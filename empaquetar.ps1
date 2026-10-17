# Genera un ZIP limpio y PORTABLE del proyecto para probarlo en otro equipo.
#
#   powershell -ExecutionPolicy Bypass -File .\empaquetar.ps1
#
# Excluye entornos virtuales, node_modules, dist, cachés y secretos
# (.env.local, .neon). Escribe las rutas con "/" para que el ZIP se extraiga
# correctamente en Windows, Linux y macOS. Resultado: "pos-casiobsceno-mvp.zip".
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$destino = Join-Path $raiz "pos-casiobsceno-mvp.zip"
$prefijo = "pos-casiobsceno-mvp"

# Nombres de carpeta/archivo que nunca deben entrar al paquete.
$excluidos = @(
    "ven", "venv", ".venv", "node_modules", "dist", "dist-ssr",
    "__pycache__", ".git", ".idea", ".vscode", ".pytest_cache",
    ".neon", ".junie"
)

Write-Host "Empaquetando desde: $raiz"
if (Test-Path $destino) { Remove-Item $destino -Force }

$zipStream = [System.IO.File]::Open($destino, [System.IO.FileMode]::CreateNew)
$zip = New-Object System.IO.Compression.ZipArchive($zipStream, [System.IO.Compression.ZipArchiveMode]::Create)
$total = 0
try {
    Get-ChildItem -Path $raiz -Recurse -File -Force | ForEach-Object {
        $rel = $_.FullName.Substring($raiz.Length + 1)
        $partes = $rel -split '[\\/]'

        # Saltar si algún segmento de la ruta está excluido
        foreach ($p in $partes) { if ($excluidos -contains $p) { return } }

        # Saltar por extensión / nombre
        if ($_.Name -like "*.pyc") { return }
        if ($_.Name -eq ".env.local") { return }
        if ($_.Name -like "*-mvp.zip") { return }

        $nombreEntrada = $prefijo + "/" + ($rel -replace '\\', '/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zip, $_.FullName, $nombreEntrada,
            [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
        $total++
    }
}
finally {
    $zip.Dispose()
    $zipStream.Dispose()
}

$mb = [math]::Round((Get-Item $destino).Length / 1MB, 2)
Write-Host "Listo: $destino ($total archivos, $mb MB)"
