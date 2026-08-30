from app import models


def _criar_programa(client, nome="Creche A", bairro="Bangu", capacidade=1):
    resp = client.post(
        "/programas",
        json={"nome": nome, "bairro": bairro, "capacidade": capacidade},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_fluxo_inscricao_ate_classificacao(client):
    programa_id = _criar_programa(client)

    resp = client.post(
        "/inscricao",
        json={
            "nome": "Maria",
            "data_nascimento": "2023-01-10",
            "responsavel_nome": "Joana",
            "responsavel_telefone": "+5521999990000",
            "bairro": "Bangu",
            "preferencias": [
                {"programa_id": programa_id, "faixa_etaria": "0-2", "turno": "manha"}
            ],
            "respostas_vulnerabilidade": {"renda_baixa": True, "familia_monoparental": True},
        },
    )
    assert resp.status_code == 200
    crianca = resp.json()
    assert crianca["score"] == 5.0  # 3.0 (renda_baixa) + 2.0 (familia_monoparental)
    crianca_id = crianca["id"]

    resp = client.post(f"/verificacao_documentos/{crianca_id}")
    assert resp.status_code == 200
    assert resp.json()["programa_escolhido_id"] == programa_id

    resp = client.get(f"/classificacao/{crianca_id}")
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["posicao_na_fila"] == 1
    assert dados["pode_alterar_escolha"] is True

    resp = client.post(
        "/avancar_processo", json={"crianca_id": crianca_id, "novo_status": "selecionado"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "selecionado"


def test_avancar_processo_sem_unidade_falha(client):
    resp = client.post(
        "/inscricao",
        json={
            "nome": "Pedro",
            "data_nascimento": "2023-05-10",
            "responsavel_nome": "Carlos",
            "responsavel_telefone": "+5521999990001",
            "bairro": "Realengo",
            "preferencias": [],
        },
    )
    crianca_id = resp.json()["id"]
    resp = client.post(
        "/avancar_processo", json={"crianca_id": crianca_id, "novo_status": "selecionado"}
    )
    assert resp.status_code == 400


def test_escolher_unidade_fora_da_janela(client, db_session):
    import datetime as dt

    programa_id = _criar_programa(client)
    outro_programa_id = _criar_programa(client, nome="Creche B")

    resp = client.post(
        "/inscricao",
        json={
            "nome": "Ana",
            "data_nascimento": "2023-02-10",
            "responsavel_nome": "Sonia",
            "responsavel_telefone": "+5521999990002",
            "bairro": "Bangu",
            "preferencias": [
                {"programa_id": programa_id, "faixa_etaria": "0-2", "turno": "manha"},
                {"programa_id": outro_programa_id, "faixa_etaria": "0-2", "turno": "manha"},
            ],
        },
    )
    crianca_id = resp.json()["id"]
    client.post(f"/verificacao_documentos/{crianca_id}")

    crianca = db_session.get(models.Crianca, crianca_id)
    crianca.escolhido_em = dt.datetime.utcnow() - dt.timedelta(days=10)
    db_session.add(crianca)
    db_session.commit()

    resp = client.post(
        "/escolher_unidade", params={"crianca_id": crianca_id, "programa_id": outro_programa_id}
    )
    assert resp.status_code == 400


def test_whatsapp_webhook_status_sem_inscricao(client):
    resp = client.post(
        "/whatsapp/webhook", data={"From": "whatsapp:+5521888880000", "Body": "status"}
    )
    assert resp.status_code == 200
    assert "INSCRICAO" in resp.text.upper()


def test_verificacao_mensal_telefone(client, db_session):
    programa_id = _criar_programa(client)
    resp = client.post(
        "/inscricao",
        json={
            "nome": "Joao",
            "data_nascimento": "2023-03-10",
            "responsavel_nome": "Rita",
            "responsavel_telefone": "+5521999990003",
            "bairro": "Bangu",
            "preferencias": [
                {"programa_id": programa_id, "faixa_etaria": "0-2", "turno": "manha"}
            ],
        },
    )
    crianca_id = resp.json()["id"]

    import datetime as dt

    crianca = db_session.get(models.Crianca, crianca_id)
    crianca.telefone_confirmado_em = dt.datetime.utcnow() - dt.timedelta(days=40)
    db_session.add(crianca)
    db_session.commit()

    resp = client.post("/jobs/verificar_telefones")
    assert resp.status_code == 200
    assert resp.json()["mensagens_enviadas"] == 1

    resp = client.post(
        "/whatsapp/webhook", data={"From": "whatsapp:+5521999990003", "Body": "SIM"}
    )
    assert resp.status_code == 200
    assert "confirmado" in resp.text.lower()

    db_session.refresh(crianca)
    assert crianca.telefone_verificacao_pendente is False


def test_inscricao_via_whatsapp(client, db_session):
    from app.classification_engine import REGUA_PADRAO

    programa_id = _criar_programa(client, nome="Creche Via WhatsApp")
    telefone_e164 = "+5521777770000"
    telefone = f"whatsapp:{telefone_e164}"

    passos = [
        "inscricao",
        "Lucas Silva",
        "2023-06-01",
        "Fernanda Silva",
        "Bangu",
        "pular",
        str(programa_id),
    ] + ["sim"] * len(REGUA_PADRAO)

    resposta = None
    for passo in passos:
        resposta = client.post("/whatsapp/webhook", data={"From": telefone, "Body": passo})
        assert resposta.status_code == 200

    assert "recebida com sucesso" in resposta.text.lower()

    crianca = (
        db_session.query(models.Crianca)
        .filter(models.Crianca.responsavel_telefone == telefone_e164)
        .one()
    )
    assert crianca.canal_inscricao == "whatsapp"
    assert crianca.nome == "Lucas Silva"
    assert crianca.preferencias[0].programa_id == programa_id
