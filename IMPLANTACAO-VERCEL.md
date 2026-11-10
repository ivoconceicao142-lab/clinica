# Adaptação para Vercel - 10/11/2026

Preparada no mesmo repositório e pasta. Não publicada por esta atualização. Não homologada para dados reais.

## O que mudou
- Vercel usa PostgreSQL por DATABASE_URL; sem variável, retorna erro controlado de configuração em vez de criar dados no disco somente leitura. Nunca usa SQLite temporário.
- Uso local sem VERCEL/DATABASE_URL conserva SQLite e os cadastros existentes.
- handler exportado para o runtime Python, dependência psycopg declarada e Python 3.12 selecionado.
- Origem pública deve corresponder exatamente a CLINICA_ORIGIN. Cookies HTTPS seguros; hosts de preview não são liberados automaticamente.
- Sessões e identificação da instalação persistem no PostgreSQL. Operações são serializadas por trava transacional para manter saldo, agenda e idempotência entre instâncias. Adequado ao escopo pequeno; não é ensaio de carga.
- Limite de login por conta armazenado no banco, além do limite local de processo.
- Primeiro administrador online só por ferramenta administrativa; cadastro inicial público desativado. Usuários adicionais exigem administrador autenticado.
- Botão de backup informa corretamente que o backup online precisa ser feito pelo provedor; não finge salvar cópia persistente no servidor Vercel.

## Configuração pendente - não envie ainda pacientes reais
1. Criar um PostgreSQL exclusivo, avaliando região, TLS, custos, retenção e restauração de backups. Nenhuma contratação foi feita.
2. No painel Vercel > Settings > Environment Variables, cadastrar DATABASE_URL (credencial secreta do provedor, com sslmode=require ou mais forte) e CLINICA_ORIGIN=https://clinica-r4fd.vercel.app (sem barra final). Confirmar o domínio real do projeto antes de usar este valor. Não colocar no GitHub.
3. Configurar o primeiro administrador em terminal local confiável: com Python 3.12 e pip disponíveis, executar `py -3.12 -m pip install -r requirements.txt` e `py -3.12 configurar_banco.py`. A ferramenta pede a conexão e a senha sem exibir. O Python embutido do pacote local não inclui pip. Não colocar a conexão na linha de comando nem no chat.
4. Revisar o diff, publicar os arquivos de código e aguardar a nova implantação. Usar o domínio estável configurado, não a URL aleatória de preview.
5. Ensaiar com dados fictícios: login de dois usuários, entrada/saída, recebimento/estorno, desconexão/reconexão, conflito, nova implantação preservando registros e restauração externa.
6. Conferir cadastros reais eventualmente presentes no SQLite antes de planejar migração. Esta alteração NÃO migra dados locais. Nenhum SQLite foi enviado ou substituído.

## Verificação realizada
Regressão local de domínio, equipe, usuários e setup passou (32 execuções, incluindo testes herdados repetidos). Mais 3 testes passaram: importação no modo Vercel sem criar diretório, compatibilidade de linhas e tradução SQL com driver simulado. Sintaxe Python e JavaScript validada.
NÃO testado: conexão PostgreSQL real, concorrência real no PostgreSQL, implantação Vercel atualizada, navegador multiaparelho, restauração PostgreSQL e migração. Esses testes são bloqueadores de liberação. Testes simulados não substituem integração.

## Segurança e operação pendentes
Recuperação/troca de senha segura, política de acesso offline/revogação, backup externo automático/restaurável, monitoramento e validação clínica continuam pendentes. Não afirmar pronto para produção apenas porque a página abrir.

## Backup e retorno
Backups anteriores à mudança estão em backups/antes-vercel-*.zip e .sqlite, ignorados pelo Git. Para voltar localmente, encerrar o sistema e restaurar os arquivos de código. Não sobrescrever bancos com alterações novas. A reversão da versão Vercel anterior continuará com a incompatibilidade SQLite; não é uma versão operacional na nuvem.
