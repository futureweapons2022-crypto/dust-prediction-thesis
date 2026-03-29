# AppData breakdown
$appdata_dirs = @('Local', 'LocalLow', 'Roaming')
foreach ($sub in $appdata_dirs) {
    $path = "C:\Users\LENOVO\AppData\$sub"
    $folders = Get-ChildItem $path -Directory -ErrorAction SilentlyContinue
    foreach ($f in $folders) {
        $size = (Get-ChildItem $f.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $mb = [math]::Round($size/1MB, 0)
        if ($mb -gt 200) {
            Write-Output "$mb MB  AppData\$sub\$($f.Name)"
        }
    }
}

# Temp folder
$tempSize = (Get-ChildItem 'C:\Users\LENOVO\AppData\Local\Temp' -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Write-Output "$([math]::Round($tempSize/1MB,0)) MB  TEMP FILES"

# npm cache
$npmSize = (Get-ChildItem 'C:\Users\LENOVO\AppData\Local\npm-cache' -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Write-Output "$([math]::Round($npmSize/1MB,0)) MB  npm-cache"

# Windows Temp
$wintempSize = (Get-ChildItem 'C:\Windows\Temp' -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Write-Output "$([math]::Round($wintempSize/1MB,0)) MB  Windows\Temp"
