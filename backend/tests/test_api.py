from app import models


def _criar_programa(client, nome="Creche A", bairro="Bangu", capacidade=1):
    resp = client.post(
        "/programas",
        json={"nome": nome, "bairro": bairro, "capacidade": capacidade},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _payload_meta(telefone_e164, texto):
    """Monta um payload de webhook no formato da Meta WhatsApp Cloud API.
    `telefone_e164` deve vir com o '+' -- a Meta manda so os digitos, entao
    removemos aqui pra imitar o formato real de 'from'."""
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": telefone_e164.lstrip("+"), "text": {"body": texto}}
                            ]
                        }
                    }
                ]
            }
        ]
    }


def _ultima_notificacao(db_session, telefone_e164):
    return (
        db_session.query(models.Notificacao)
        .filter(models.Notificacao.telefone == telefone_e164)
        .order_by(models.Notificacao.created_at.desc())
        .first()
    )


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
            "respostas_vulnerabilidade": {"6": True, "20": True},
        },
    )
    assert resp.status_code == 200
    crianca = resp.json()
    assert crianca["score"] == 6.0  # 2.0 (bolsa familia) + 4.0 (familia monoparental)
    assert crianca["token"]  # login automatico ao se inscrever
    crianca_id = crianca["id"]
    headers = _auth_headers(crianca["token"])

    resp = client.post(f"/verificacao_documentos/{crianca_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["programa_escolhido_id"] == programa_id

    resp = client.get(f"/classificacao/{crianca_id}", headers=headers)
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
    headers = _auth_headers(resp.json()["token"])
    client.post(f"/verificacao_documentos/{crianca_id}", headers=headers)

    crianca = db_session.get(models.Crianca, crianca_id)
    crianca.escolhido_em = dt.datetime.utcnow() - dt.timedelta(days=10)
    db_session.add(crianca)
    db_session.commit()

    resp = client.post(
        "/escolher_unidade",
        params={"crianca_id": crianca_id, "programa_id": outro_programa_id},
        headers=headers,
    )
    assert resp.status_code == 400


def test_login_por_codigo_e_dono_da_inscricao(client, db_session):
    programa_id = _criar_programa(client)
    telefone = "+5521999990099"
    resp = client.post(
        "/inscricao",
        json={
            "nome": "Beatriz",
            "data_nascimento": "2023-04-10",
            "responsavel_nome": "Marcia",
            "responsavel_telefone": telefone,
            "bairro": "Bangu",
            "preferencias": [
                {"programa_id": programa_id, "faixa_etaria": "0-2", "turno": "manha"}
            ],
        },
    )
    crianca_id = resp.json()["id"]

    # sem token nao entra
    assert client.get(f"/classificacao/{crianca_id}").status_code == 401

    # solicita o codigo e confere no banco (sem depender do Twilio de verdade)
    assert client.post("/auth/solicitar-codigo", json={"telefone": telefone}).status_code == 200
    codigo = (
        db_session.query(models.CodigoLogin)
        .filter(models.CodigoLogin.telefone == telefone)
        .order_by(models.CodigoLogin.created_at.desc())
        .first()
    )
    assert codigo is not None

    resp = client.post("/auth/verificar-codigo", json={"telefone": telefone, "codigo": codigo.codigo})
    assert resp.status_code == 200
    token = resp.json()["token"]

    resp = client.get("/minhas-inscricoes", headers=_auth_headers(token))
    assert resp.status_code == 200
    assert [c["id"] for c in resp.json()] == [crianca_id]

    # o numero de outra familia nao pode ver essa inscricao
    outro_token = client.post(
        "/inscricao",
        json={
            "nome": "Outro",
            "data_nascimento": "2023-01-01",
            "responsavel_nome": "Fulano",
            "responsavel_telefone": "+5521999990100",
            "bairro": "Bangu",
            "preferencias": [],
        },
    ).json()["token"]
    resp = client.get(f"/classificacao/{crianca_id}", headers=_auth_headers(outro_token))
    assert resp.status_code == 403


def test_whatsapp_webhook_status_sem_inscricao(client, db_session):
    telefone = "+5521888880000"
    resp = client.post("/whatsapp/webhook", json=_payload_meta(telefone, "status"))
    assert resp.status_code == 200
    notificacao = _ultima_notificacao(db_session, telefone)
    assert "INSCRICAO" in notificacao.corpo.upper()


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

    telefone = "+5521999990003"
    resp = client.post("/whatsapp/webhook", json=_payload_meta(telefone, "SIM"))
    assert resp.status_code == 200
    notificacao = _ultima_notificacao(db_session, telefone)
    assert "confirmado" in notificacao.corpo.lower()

    db_session.refresh(crianca)
    assert crianca.telefone_verificacao_pendente is False


def test_inscricao_via_whatsapp(client, db_session):
    from app.classification_engine import REGUA_PADRAO

    programa_id = _criar_programa(client, nome="Creche Via WhatsApp")
    telefone_e164 = "+5521777770000"

    passos = [
        "inscricao",
        "Lucas Silva",
        "2023-06-01",
        "Fernanda Silva",
        "Bangu",
        "pular",
        str(programa_id),
    ] + ["sim"] * len(REGUA_PADRAO)

    for passo in passos:
        resp = client.post("/whatsapp/webhook", json=_payload_meta(telefone_e164, passo))
        assert resp.status_code == 200

    notificacao = _ultima_notificacao(db_session, telefone_e164)
    assert "recebida com sucesso" in notificacao.corpo.lower()

    crianca = (
        db_session.query(models.Crianca)
        .filter(models.Crianca.responsavel_telefone == telefone_e164)
        .one()
    )
    assert crianca.canal_inscricao == "whatsapp"
    assert crianca.nome == "Lucas Silva"
    assert crianca.preferencias[0].programa_id == programa_id
