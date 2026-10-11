<#
Modo teste da maquina de casa: libera CPU, RAM e GPU para uma rodada pesada do benchmark e depois desfaz.

O que faz (padrao = SO MOSTRA; nada muda sem -Aplicar):
  1. fecha os programas de uma LISTA explicita (abaixo), que estavam abertos nesta maquina em 11/10/2026 e nao
     tem nada a ver com os testes. Nunca toca no VS Code (Code), no Claude Code (claude), no terminal, nos
     ambientes Python nem em processos do Windows. O navegador (Brave) so fecha com -FecharNavegador (abas!);
  2. pausa o OneDrive (fecha o cliente; a sincronizacao volta ao reabrir);
  3. troca o plano de energia para "Alto desempenho" (processador sem economia) e guarda o plano anterior;
  4. -Prioridade: sobe para AboveNormal os python.exe que ja estiverem rodando (nunca Realtime: trava a maquina);
  5. GPU: mostra o limite de potencia (padrao 200 W, maximo 216 W na RTX 4070). Subir para 216 W esta DENTRO da
     especificacao (nao e overclock) mas exige administrador: o script imprime o comando, nao executa.
  -Restaurar: volta o plano de energia anterior e reabre os programas fechados que tinham caminho conhecido.

O que NAO faz, de proposito:
  - overclock de CPU ou GPU (XTU, MSI Afterburner, offsets de clock/tensao): pode mudar resultados numericos e quebrar
    a reprodutibilidade do benchmark, aquece e nao e desfeito por este script; o ganho real para os nossos testes e
    pequeno (o gargalo medido e memoria, nao clock);
  - desligar o Windows Defender ou o Smart App Control (este e irreversivel; ver CLAUDE.md);
  - mexer em servicos do Windows.

Uso (PowerShell, de qualquer pasta):
  .\modo_teste.ps1                         # mostra o que faria e quanto de memoria liberaria
  .\modo_teste.ps1 -Aplicar                # liga o modo teste
  .\modo_teste.ps1 -Aplicar -FecharNavegador -Prioridade
  .\modo_teste.ps1 -Restaurar              # desliga
Estado guardado em %LOCALAPPDATA%\prosumer_modo_teste.json.
#>
param([switch]$Aplicar, [switch]$Restaurar, [switch]$FecharNavegador, [switch]$Prioridade)

$ErrorActionPreference = 'Continue'
$estado = Join-Path $env:LOCALAPPDATA 'prosumer_modo_teste.json'
$ALTO = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'   # "Alto desempenho" (existe nesta maquina)

# Programas que podem fechar: nome do processo -> descricao. Lista explicita; acrescentar aqui o que aparecer.
$FECHAR = [ordered]@{
    'steam' = 'Steam'; 'steamwebhelper' = 'Steam (navegador interno)'; 'Discord' = 'Discord'
    'wallpaper64' = 'Wallpaper Engine'; 'wallpaper32' = 'Wallpaper Engine'
    'lghub' = 'Logitech G Hub'; 'lghub_agent' = 'Logitech G Hub'; 'lghub_system_tray' = 'Logitech G Hub'; 'lghub_updater' = 'Logitech G Hub'
    'GCC' = 'Gigabyte Control Center'; 'GBT_DL_LIB' = 'Gigabyte (biblioteca de download)'; 'NGenuity2Helper' = 'HyperX NGenuity'
    'XboxPcTray' = 'Xbox'; 'XboxPcApp' = 'Xbox'; 'M365Copilot' = 'Microsoft 365 Copilot'
    'ollama app' = 'Ollama (bandeja)'; 'ollama' = 'Ollama (servidor: pode segurar memoria da GPU)'
    'SnippingTool' = 'Ferramenta de Captura'; 'PhoneExperienceHost' = 'Link para o Celular'; 'CrossDeviceResume' = 'Retomar entre dispositivos'
    'Spotify' = 'Spotify'; 'ms-teams' = 'Teams'; 'Teams' = 'Teams'; 'EpicGamesLauncher' = 'Epic Games'
    'OneDrive' = 'OneDrive (pausa a sincronizacao)'
}
if ($FecharNavegador) { $FECHAR['brave'] = 'Brave (as abas voltam ao reabrir, se a restauracao de sessao estiver ligada)' }
$NUNCA = @('Code', 'claude', 'node', 'python', 'pythonw', 'uv', 'bash', 'powershell', 'pwsh', 'WindowsTerminal', 'OpenConsole', 'conhost', 'git')

function Memoria {
    $os = Get-CimInstance Win32_OperatingSystem
    '{0:N1} GB livres de {1:N1} GB' -f ($os.FreePhysicalMemory / 1MB), ($os.TotalVisibleMemorySize / 1MB)
}
function Gpu {
    & nvidia-smi --query-gpu=memory.used,memory.total,power.limit,power.max_limit,temperature.gpu --format=csv,noheader 2>$null
}

if ($Restaurar) {
    if (-not (Test-Path $estado)) { Write-Host 'Nada a restaurar (modo teste nao estava ligado).'; exit 0 }
    $s = Get-Content $estado -Raw | ConvertFrom-Json
    powercfg /setactive $s.plano_anterior | Out-Null
    Write-Host "Plano de energia restaurado: $($s.plano_anterior)"
    foreach ($c in $s.reabrir) {
        if ($c -and (Test-Path $c)) { Start-Process -FilePath $c -WindowStyle Minimized -ErrorAction SilentlyContinue; Write-Host "Reaberto: $c" }
    }
    Remove-Item $estado
    Write-Host "Memoria: $(Memoria) | GPU: $(Gpu)"
    exit 0
}

# --- o que esta aberto e seria fechado
$alvos = Get-Process | Where-Object { $FECHAR.Contains($_.ProcessName) -and $NUNCA -notcontains $_.ProcessName }
$grupos = $alvos | Group-Object ProcessName | ForEach-Object {
    [pscustomobject]@{ Processo = $_.Name; Programa = $FECHAR[$_.Name]; N = $_.Count
                       MB = [math]::Round(($_.Group | Measure-Object PrivateMemorySize64 -Sum).Sum / 1MB) }
} | Sort-Object MB -Descending
Write-Host "Antes: memoria $(Memoria) | GPU (usada, total, limite, maximo, temp): $(Gpu)"
if ($grupos) { $grupos | Format-Table -AutoSize | Out-String -Width 120 | Write-Host } else { Write-Host 'Nenhum programa da lista aberto.' }
Write-Host ('Liberaria ~{0:N1} GB de memoria privada.' -f (($grupos | Measure-Object MB -Sum).Sum / 1024))
$plano = ((powercfg /getactivescheme) -replace '.*:\s*([0-9a-f-]{36}).*', '$1').Trim()
Write-Host "Plano de energia atual: $plano -> Alto desempenho ($ALTO)"
Write-Host 'GPU, opcional e so como administrador (dentro da especificacao, nao e overclock):  nvidia-smi -pl 216   (desfazer: nvidia-smi -pl 200)'

if (-not $Aplicar) { Write-Host "`nSo mostrei. Para ligar: .\modo_teste.ps1 -Aplicar"; exit 0 }

# --- liga
$reabrir = @($alvos | ForEach-Object { try { $_.MainModule.FileName } catch { $null } } | Where-Object { $_ } | Sort-Object -Unique)
if (-not (Test-Path $estado)) {   # nao sobrescreve o plano anterior se ja estava ligado
    @{ plano_anterior = $plano; reabrir = $reabrir; quando = (Get-Date).ToString('s') } | ConvertTo-Json | Set-Content $estado -Encoding utf8
}
foreach ($p in $alvos) {
    try { $p.CloseMainWindow() | Out-Null } catch {}
}
Start-Sleep -Seconds 3
Get-Process | Where-Object { $FECHAR.Contains($_.ProcessName) -and $NUNCA -notcontains $_.ProcessName } |
    Stop-Process -Force -ErrorAction SilentlyContinue
powercfg /setactive $ALTO | Out-Null
if ($Prioridade) {
    Get-Process python, pythonw -ErrorAction SilentlyContinue | ForEach-Object {
        try { $_.PriorityClass = 'AboveNormal'; Write-Host "Prioridade AboveNormal: python $($_.Id)" } catch {}
    }
}
Start-Sleep -Seconds 2
Write-Host "`nModo teste LIGADO. Depois: memoria $(Memoria) | GPU: $(Gpu)"
Write-Host 'Para desligar: .\modo_teste.ps1 -Restaurar'
