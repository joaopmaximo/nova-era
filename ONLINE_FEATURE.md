# Funcionalidade de Status Online (Desativada)

Esta funcionalidade permitia marcar alunos como "Online" ou "Offline" e filtrar a listagem com base nesse estado. Atualmente, ela está **desativada na interface (UI)**, mas preservada no banco de dados e no backend.

## Estrutura Técnica
- **Banco de Dados:** Coluna `is_online` (Boolean) na tabela `students`.
- **Backend:** O endpoint `GET /` ainda aceita o parâmetro `online=true`, e os endpoints de cadastro/atualização ainda processam o campo `is_online`.
- **CSV:** A importação e exportação ainda incluem a coluna "Online".

## Como Reativar na Interface

Para tornar a funcionalidade visível novamente, siga estes passos no arquivo `templates/students.html`:

1.  **Filtro de Listagem:** Re-adicionar o componente de toggle (Todos/Online) ao lado da barra de pesquisa.
2.  **Badge na Tabela:** Descomentar ou re-adicionar o `<span>` que exibe o status verde (Online) ou cinza (Offline) na primeira coluna da tabela.
3.  **Formulários:** Alterar os campos `<input type="hidden" name="is_online">` para `<input type="checkbox">` tanto no `registerForm` quanto no `editForm`.
4.  **JavaScript:** No `editModal`, garantir que o valor do checkbox seja definido corretamente (`cb.checked = student.is_online`).

## Histórico
- **Implementada em:** 08/05/2026
- **Desativada em:** 08/05/2026 (Para simplificação da UI a pedido do usuário).
