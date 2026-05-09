# Funcionalidade de Status Online (Desativada)

Esta funcionalidade permitia marcar alunos como "Online" ou "Offline" e filtrar a listagem com base nesse estado. Atualmente, ela está **desativada na interface (UI)**, mas preservada no banco de dados e no backend.

## Estrutura Técnica
- **Banco de Dados:** Coluna `is_online` (Boolean) na tabela `students`.
- **Backend:** O endpoint `GET /` ainda aceita o parâmetro `online=true` (embora não haja link na UI), e os endpoints de cadastro/atualização manuais via modal ainda podem processar o campo caso sejam reativados.
- **CSV:** A importação e exportação **não** incluem mais a coluna "Online" para manter o padrão da interface simplificada.

## Como Reativar Completamente

Para tornar a funcionalidade visível e funcional novamente:

1.  **Filtro de Listagem:** Re-adicionar o componente de toggle (Todos/Online) ao lado da barra de pesquisa no `students.html`.
2.  **Badge na Tabela:** Re-adicionar a coluna de Status na tabela do `students.html`.
3.  **Formulários:** Alterar os campos ocultos para checkboxes nos formulários de cadastro e edição.
4.  **CSV:** Re-adicionar a lógica de leitura/escrita do campo `is_online` nas funções `export_csv` e `import_csv` no `app/main.py`.

## Histórico
- **Implementada em:** 08/05/2026
- **Desativada em:** 08/05/2026 (Para simplificação da UI a pedido do usuário).
