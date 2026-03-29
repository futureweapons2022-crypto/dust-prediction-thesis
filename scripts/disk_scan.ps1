$folders = Get-ChildItem 'C:\Users\LENOVO' -Directory -ErrorAction SilentlyContinue
foreach ($f in $folders) {
    $size = (Get-ChildItem $f.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    $mb = [math]::Round($size/1MB, 0)
    if ($mb -gt 50) {
        Write-Output "$mb MB  $($f.Name)"
    }
}
