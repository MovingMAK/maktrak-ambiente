# AI Agent Guide — regras restritas deste repositório

Regras específicas deste repositório para agentes de IA. As diretivas gerais ficam em
`AI_agent_guide_generic.md`, no repositório público `maktrak-ambiente`; ele pode não
estar presente no workspace local, então use o link:

<https://raw.githubusercontent.com/MovingMAK/maktrak-ambiente/main/AI_agent_guide_generic.md>

## Regras deste repositório

- Valide mudança de setup em VM antes de aplicar na máquina real.
- Os scripts são idempotentes e rodam como usuário normal, com sudo apenas
  internamente. `setup_windows.ps1` e `setup-linux.sh` devem andar em paridade.
- Ao alterar o setup, buipe `SETUP_VERSION` em `maktrak_setup.py`.
