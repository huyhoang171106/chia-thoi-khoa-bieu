$ErrorActionPreference = 'Stop'
try {
    $builder = New-Object System.Data.SqlClient.SqlConnectionStringBuilder
    $builder['Data Source'] = 'tcp:' + $env:LT_DB_HOST + ',' + $env:LT_DB_PORT
    $builder['Initial Catalog'] = $env:LT_DB_NAME
    $builder['User ID'] = $env:LT_DB_USER
    $builder['Password'] = $env:LT_DB_PASSWORD
    $builder['Connect Timeout'] = 10
    $builder['Encrypt'] = $true
    $builder['TrustServerCertificate'] = $env:LT_DB_HOST -in @('localhost', '127.0.0.1')
    $sql = [Console]::In.ReadToEnd()
    $connection = New-Object System.Data.SqlClient.SqlConnection($builder.ConnectionString)
    try {
        $connection.Open()
        $command = $connection.CreateCommand()
        $command.CommandText = $sql
        $command.CommandTimeout = 10
        $reader = $command.ExecuteReader()
        try {
            while ($reader.Read()) { if (-not $reader.IsDBNull(0)) { [Console]::Out.Write($reader.GetValue(0)) } }
        } finally { $reader.Close() }
    } finally { $connection.Close() }
} catch [System.Data.SqlClient.SqlException] {
    $number = $_.Exception.Number
    if ($number -eq 18456) { [Console]::Error.Write('LOGIN') }
    elseif ($number -eq 4060) { [Console]::Error.Write('DATABASE') }
    elseif ($number -eq 229 -or $number -eq 262 -or $number -eq 2760) { [Console]::Error.Write('PERMISSION') }
    else { [Console]::Error.Write('SQL_ERROR') }
    exit 1
} catch { [Console]::Error.Write('CONNECTION'); exit 1 }
