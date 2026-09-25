import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def _load(name, filename):
    """Carrega um modulo do repo pelo caminho (mesmo padrao do test de git)."""
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


maktrak_setup = _load("maktrak_setup", "maktrak_setup.py")
server_setup = _load("server_setup", "server_setup.py")


class _FakeResp:
    """Context manager minimo que devolve um corpo fixo (substitui urlopen)."""

    def __init__(self, dados):
        self._dados = dados

    def read(self):
        return self._dados

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class ProducaoNoOrquestradorTests(unittest.TestCase):
    """O modo prod nao pode clonar repositorio nem instalar software de dev."""

    def test_prod_nao_clona_repositorios(self):
        self.assertEqual(
            maktrak_setup._get_repositories_to_clone("prod", ["servidor-prod"]),
            [],
        )
        self.assertEqual(
            maktrak_setup._get_repositories_to_clone(
                "prod", ["servidor-prod", "ia"]),
            [],
        )

    def test_prod_nao_instala_software_de_dev(self):
        self.assertEqual(
            maktrak_setup._get_software_for_components(
                ["servidor-prod"], "prod"),
            [],
        )

    def test_dev_continua_clonando_o_servidor(self):
        """Guarda de paridade: o modo dev nao pode perder o comportamento."""
        self.assertEqual(
            maktrak_setup._get_repositories_to_clone("dev", ["servidor"]),
            ["servidores"],
        )
        self.assertIn(
            "vscode",
            maktrak_setup._get_software_for_components(["servidor"], "dev"),
        )

    def test_delegate_tenta_a_branch_e_cai_para_main(self):
        urls = []

        def fake_urlopen(url, timeout=0):
            urls.append(url)
            if "/main/" in url:
                return _FakeResp(b"# server_setup")
            raise OSError("branch inexistente neste repo")

        with mock.patch.object(maktrak_setup.urllib.request, "urlopen",
                               fake_urlopen), \
                mock.patch.object(maktrak_setup.subprocess, "run") as run:
            run.return_value.returncode = 0
            rc = maktrak_setup._delegate_prod_setup("minha-branch")

        self.assertEqual(rc, 0)
        self.assertIn("/minha-branch/server_setup.py", urls[0])
        self.assertIn("/main/server_setup.py", urls[1])
        argv = run.call_args[0][0]
        self.assertTrue(argv[1].endswith("server_setup.py"))
        self.assertEqual(argv[2:], ["--branch", "minha-branch"])

    def test_delegate_nao_repete_main_quando_ja_e_main(self):
        urls = []

        def fake_urlopen(url, timeout=0):
            urls.append(url)
            return _FakeResp(b"# server_setup")

        with mock.patch.object(maktrak_setup.urllib.request, "urlopen",
                               fake_urlopen), \
                mock.patch.object(maktrak_setup.subprocess, "run") as run:
            run.return_value.returncode = 0
            maktrak_setup._delegate_prod_setup("main")

        self.assertEqual(len(urls), 1)
        self.assertIn("/main/server_setup.py", urls[0])

    def test_delegate_falha_sem_rede(self):
        def fake_urlopen(url, timeout=0):
            raise OSError("sem rede")

        with mock.patch.object(maktrak_setup.urllib.request, "urlopen",
                               fake_urlopen):
            self.assertEqual(maktrak_setup._delegate_prod_setup("main"), 1)


class ServerSetupTests(unittest.TestCase):
    """O server_setup.py precisa ser autossuficiente e idempotente."""

    def test_nao_depende_do_orquestrador(self):
        fonte = (ROOT / "server_setup.py").read_text(encoding="utf-8")
        self.assertNotIn("import maktrak_setup", fonte)
        self.assertNotIn("from maktrak_setup import", fonte)

    def test_recebedor_completo(self):
        """`deploy_receiver` -> `deploy` -> `errors`: os tres andam juntos."""
        self.assertEqual(set(server_setup.ARQUIVOS_RECEBEDOR), {
            "server_api/exec/deploy.py",
            "server_api/exec/deploy_receiver.py",
            "server_api/exec/errors.py",
        })

    def test_versao_declarada(self):
        self.assertTrue(server_setup.SETUP_VERSION)
        self.assertTrue(server_setup.SETUP_DATE)

    def test_unit_exposta_na_rede(self):
        alvo = Path("/srv/proj")
        texto = server_setup.unit_text(
            "maktrak", alvo, 8001, True, "/opt/venv/bin/python")
        self.assertIn("User=maktrak", texto)
        self.assertIn("Restart=always", texto)
        self.assertIn(f"WorkingDirectory={alvo / 'server_api'}", texto)
        self.assertIn(f"ExecStart=/opt/venv/bin/python "
                      f"{alvo / 'server_api' / 'exec' / 'deploy_receiver.py'} "
                      f"--port 8001 --extern", texto)
        self.assertIn("[Install]", texto)

    def test_unit_apenas_local(self):
        texto = server_setup.unit_text("u", Path("/p"), 9001, False, "/py")
        self.assertIn("--port 9001", texto)
        self.assertNotIn("--extern", texto)

    def test_alvo_e_porta_default(self):
        self.assertEqual(server_setup.PORTA_PADRAO, 8001)
        self.assertEqual(server_setup.ALVO_PADRAO,
                         Path.home() / "maktrak-server")

    def test_gravar_se_mudou_e_idempotente(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            destino = Path(tmpdir) / "deploy.py"
            self.assertTrue(server_setup._gravar_se_mudou(destino, b"abc"))
            self.assertFalse(server_setup._gravar_se_mudou(destino, b"abc"))
            self.assertTrue(server_setup._gravar_se_mudou(destino, b"abcd"))
            self.assertEqual(destino.read_bytes(), b"abcd")

    def test_sem_token_nao_instala_recebedor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ok, mudou = server_setup.instalar_recebedor(
                Path(tmpdir), "main", "")
            self.assertFalse(ok)
            self.assertFalse(mudou)
            self.assertFalse((Path(tmpdir) / "server_api").exists())

    def test_requisitos_fora_do_linux(self):
        original = server_setup.OS_TYPE
        try:
            server_setup.OS_TYPE = "windows"
            ok, motivo = server_setup.checar_requisitos()
            self.assertFalse(ok)
            self.assertIn("windows", motivo)
        finally:
            server_setup.OS_TYPE = original


if __name__ == "__main__":
    unittest.main()
