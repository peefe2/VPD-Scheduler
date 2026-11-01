# VPD Scheduler 실행: 백엔드 창과 프론트 창을 따로 열고 브라우저를 띄운다.
# 더블클릭은 start.cmd 로 한다. 끄려면 "VPD 백엔드", "VPD 프론트" 창을 닫는다.

$root = $PSScriptRoot
$envFile = Join-Path $root 'backend\.env'

function Stop-WithMessage($msg) {
    Write-Host $msg -ForegroundColor Yellow
    Read-Host '엔터를 누르면 닫힙니다'
    exit 1
}

foreach ($cmd in 'uv', 'npm') {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Stop-WithMessage "$cmd 가 설치되어 있지 않습니다. README의 '설치' 부분을 먼저 해 주세요."
    }
}
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    Stop-WithMessage '8000번 포트를 이미 쓰고 있습니다. 전에 켠 "VPD 백엔드" 창을 닫고 다시 실행해 주세요.'
}

# 처음이면 .env를 만들고 메모장으로 연다 — 키를 넣고 저장한 뒤 메모장을 닫으면 계속한다
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $root 'backend\.env.example') $envFile
    Write-Host '처음 실행이라 backend\.env 를 만들었습니다.'
    Write-Host 'GEMINI_API_KEY= 뒤에 키를 붙여 넣고 저장한 다음 메모장을 닫으세요.'
    Write-Host '(키가 없으면 그냥 닫아도 됩니다. AI 어드바이저가 규칙 기반 안내로 답합니다.)'
    Start-Process notepad $envFile -Wait
}

if (-not (Test-Path (Join-Path $root 'frontend\node_modules'))) {
    Write-Host '프론트 패키지를 처음 설치합니다 (1~2분)...'
    Push-Location (Join-Path $root 'frontend')
    npm install
    Pop-Location
}

Start-Process powershell -ArgumentList '-NoExit', '-Command',
    "`$Host.UI.RawUI.WindowTitle = 'VPD 백엔드'; Set-Location '$root\backend'; uv run uvicorn app.serve:app --port 8000"
Start-Process powershell -ArgumentList '-NoExit', '-Command',
    "`$Host.UI.RawUI.WindowTitle = 'VPD 프론트'; Set-Location '$root\frontend'; npm run dev"

# 처음엔 파이썬 패키지 설치와 데모 온실 준비로 1~3분 걸릴 수 있다
Write-Host '백엔드와 프론트를 켜는 중입니다. 준비되면 브라우저가 열립니다 (처음엔 1~3분).'
for ($i = 0; $i -lt 300; $i++) {
    $api = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    $web = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
    if ($api -and $web) { break }
    Start-Sleep -Seconds 1
}
Start-Process 'http://localhost:5173'
