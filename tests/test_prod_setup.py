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

    def __init__(self, dados, status=200):
        self._dados = dados
        self.status = status

    def read(self):
        return self._dados

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class GitAntesDoModoTests(unittest.TestCase):
    """O git tem de estar garantido antes de perguntar o modo."""

    def test_main_chama_ensure_git_antes_do_modo(self):
        fonte = (ROOT / "maktrak_setup.py").read_text(encoding="utf-8")
        # Escopo: corpo de main() (evita casar com a definicao da funcao).
        inicio = fonte.index("def main():")
        corpo = fonte[inicio:]
        pos_git = corpo.index("_ensure_git()")
        pos_modo = corpo.index("mode = _ui_select_mode()")
        self.assertLess(pos_git, pos_modo,
                        "_ensure_git() deve vir antes de _ui_select_mode()")

    def test_linux_instala_git_sem_checagem(self):
        """Linux rode sempre (idempotente): sem `if` sobre o git."""
        fonte = (ROOT / "maktrak_setup.py").read_text(encoding="utf-8")
        inicio = fonte.index("def _ensure_git():")
        fim = fonte.index("def _install_base_software():")
        bloco = fonte[inicio:fim]
        inicio_linux = bloco.index('if os_type.startswith("linux"):')
        fim_linux = bloco.index('elif os_type == "windows":')
        ramo_linux = bloco[inicio_linux:fim_linux]
        self.assertIn('"--install", "-y", "git"'.replace("--install", "install"),
                      ramo_linux)
        self.assertNotIn("_git_validate()", ramo_linux)

    def test_windows_mantem_checagem(self):
        """Windows checa antes: winget instalado tentaria upgrade."""
        fonte = (ROOT / "maktrak_setup.py").read_text(encoding="utf-8")
        inicio = fonte.index('elif os_type == "windows":')
        fim = fonte.index("else:", inicio)
        self.assertIn("if _git_validate():", fonte[inicio:fim])

    def test_base_software_nao_instala_git(self):
        """O git saiu de _install_base_software (agora e responsabilidade unica)."""
        fonte = (ROOT / "maktrak_setup.py").read_text(encoding="utf-8")
        inicio = fonte.index("def _install_base_software():")
        fim = fonte.index("def _ui_select_mode():")
        self.assertNotIn('"-y", "git"', fonte[inicio:fim])


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

    def test_branch_padrao_vem_do_ambiente(self):
        """`MAKTRAK_REF` (exportado pelo bootstrap) preseleciona a branch."""
        with mock.patch.object(maktrak_setup, "input", return_value=""), \
                mock.patch.dict(maktrak_setup.os.environ,
                                {"MAKTRAK_REF": "minha-ref"}):
            ref = maktrak_setup.os.environ.get("MAKTRAK_REF") or "main"
            escolhida = maktrak_setup._ui_select_branch("Branch? ", ref)
        self.assertEqual(escolhida, "minha-ref")

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
    """O server_setup.py e um bootstrap fino: clona e delega ao instalador."""

    def test_nao_depende_do_orquestrador(self):
        fonte = (ROOT / "server_setup.py").read_text(encoding="utf-8")
        self.assertNotIn("import maktrak_setup", fonte)
        self.assertNotIn("from maktrak_setup import", fonte)

    def test_defaults(self):
        self.assertEqual(server_setup.PORTA_PADRAO, 8000)
        self.assertEqual(server_setup.DESTINO_PADRAO,
                         Path.home() / "maktrak-server")
        self.assertIn("maktrak-server.git", server_setup.REPO_SERVIDORES)

    def test_ambiente_git_sem_token(self):
        env = server_setup._ambiente_git("")
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        valores = [v for k, v in env.items() if k.startswith("GIT_CONFIG_VALUE_")]
        self.assertFalse(any(v.startswith("Authorization: Basic") for v in valores))

    def test_ambiente_git_com_token_fora_do_argv(self):
        with mock.patch.dict(server_setup.os.environ, {}, clear=True):
            env = server_setup._ambiente_git("segredo-123")
        indice = int(env["GIT_CONFIG_COUNT"]) - 1
        self.assertEqual(env[f"GIT_CONFIG_KEY_{indice}"],
                         "http.https://github.com/.extraheader")
        valor = env[f"GIT_CONFIG_VALUE_{indice}"]
        self.assertTrue(valor.startswith("Authorization: Basic "))
        self.assertNotIn("segredo-123", valor)  # vai em base64

    def test_token_do_ambiente(self):
        with mock.patch.dict(server_setup.os.environ,
                             {"GITHUB_TOKEN": " abc "}, clear=False):
            self.assertEqual(server_setup.token_do_ambiente_ou_store(), "abc")

    def test_token_do_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / ".git-credentials"
            store.write_text(
                "https://usuario:tok%40en@github.com\n", encoding="utf-8")
            with mock.patch.dict(server_setup.os.environ, {}, clear=True), \
                    mock.patch.object(Path, "home", return_value=Path(tmp)):
                self.assertEqual(
                    server_setup.token_do_ambiente_ou_store(), "tok@en")

    def test_obter_codigo_clona_raso(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "projeto"
            with mock.patch.object(server_setup, "_executar",
                                   return_value=(True, "")) as executar:
                ok, motivo = server_setup.obter_codigo(
                    destino, "minha-branch", "t")
            self.assertTrue(ok)
            self.assertEqual(motivo, "")
            argv = executar.call_args[0][0]
            self.assertEqual(argv[:4], ["git", "clone", "--depth", "1"])
            self.assertIn("--branch", argv)
            self.assertEqual(argv[argv.index("--branch") + 1], "minha-branch")

    def test_obter_codigo_atualiza_clone_existente(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "projeto"
            (destino / ".git").mkdir(parents=True)
            with mock.patch.object(server_setup, "_executar",
                                   return_value=(True, "")) as executar:
                ok, motivo = server_setup.obter_codigo(destino, "main", "t")
            self.assertTrue(ok)
            self.assertEqual(motivo, "")
            chamadas = [c[0][0] for c in executar.call_args_list]
            self.assertIn("fetch", chamadas[0])
            self.assertIn("reset", chamadas[-1])

    def test_classificar_falha_credencial(self):
        for saida in (
            "fatal: Authentication failed for 'https://github.com/x/y.git/'",
            "remote: Invalid username or token.\nfatal: Authentication failed",
            "fatal: unable to get password from user",
            "fatal: could not read Username for 'https://github.com': "
            "terminal prompts disabled",
        ):
            self.assertEqual(server_setup.classificar_falha(saida), "credencial")

    def test_classificar_falha_rede(self):
        for saida in (
            "fatal: unable to access 'https://x/': Could not resolve host: x",
            "fatal: Failed to connect to github.com port 443: Connection timed out",
            "fatal: Could not read from remote repository.",
        ):
            self.assertEqual(server_setup.classificar_falha(saida), "rede")

    def test_classificar_falha_branch(self):
        for saida in (
            "fatal: Remote branch nao-existe not found in upstream origin",
            "fatal: couldn't find remote ref refs/heads/nao-existe",
        ):
            self.assertEqual(server_setup.classificar_falha(saida), "branch")

    def test_classificar_falha_desconhecida(self):
        self.assertEqual(server_setup.classificar_falha("algo inesperado"),
                         "outro")
        self.assertEqual(server_setup.classificar_falha(""), "outro")

    def test_mensagem_falha_cita_a_causa(self):
        self.assertIn("GITHUB_TOKEN",
                      server_setup.mensagem_falha("credencial", "main", "/p"))
        self.assertIn("'minha-branch'",
                      server_setup.mensagem_falha("branch", "minha-branch", "/p"))
        self.assertIn("rede",
                      server_setup.mensagem_falha("rede", "main", "/p"))
        self.assertIn("/p",
                      server_setup.mensagem_falha("destino", "main", "/p"))

    def test_pasta_existente_sem_git_nao_clona(self):
        """Pasta ocupada não é clone: erro claro em vez de falha do git."""
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "projeto"
            destino.mkdir()
            (destino / "arquivo.txt").write_text("x")
            with mock.patch.object(server_setup, "_executar") as executar:
                ok, motivo = server_setup.obter_codigo(destino, "main", "t")
            self.assertFalse(ok)
            self.assertEqual(motivo, "destino")
            executar.assert_not_called()

    def test_nao_pede_token_em_erro_de_branch(self):
        """Só credencial abre prompt; branch/rede não."""
        fonte = (ROOT / "server_setup.py").read_text(encoding="utf-8")
        inicio = fonte.index("    token = token_do_ambiente_ou_store()")
        trecho = fonte[inicio:inicio + 700]
        self.assertIn('motivo == "credencial" and not token', trecho)

    def test_repassa_parametros_ao_instalador(self):
        """O bootstrap nao instala nada: quem faz e o install_server.py."""
        fonte = (ROOT / "server_setup.py").read_text(encoding="utf-8")
        self.assertIn('"install_server.py"', fonte)
        self.assertNotIn("systemctl", fonte)
        self.assertNotIn("schtasks", fonte)
