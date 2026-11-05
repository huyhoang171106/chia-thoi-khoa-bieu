param([Parameter(Mandatory=$true)][ValidateSet('create','drop')] [string]$Action)
$ErrorActionPreference='Stop'
$values=@{}
Get-Content -Encoding UTF8 .env | ForEach-Object { if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { $values[$matches[1]]=$matches[2].Trim().Trim('"').Trim("'") } }
$builder=New-Object System.Data.SqlClient.SqlConnectionStringBuilder
$builder['Data Source']='tcp:'+$values.DB_HOST+','+$values.DB_PORT
$builder['Initial Catalog']='master';$builder['User ID']=$values.DB_USER;$builder['Password']=$values.DB_PASSWORD
$builder['Encrypt']=$true;$builder['TrustServerCertificate']=$true
$connection=New-Object System.Data.SqlClient.SqlConnection($builder.ConnectionString)
try {
  $connection.Open();$cmd=$connection.CreateCommand()
  if($Action -eq 'create') {
    $name='LichTruongTest_'+[Guid]::NewGuid().ToString('N')
    $cmd.CommandText="CREATE DATABASE [$name]";$cmd.ExecuteNonQuery() | Out-Null
    $connection.ChangeDatabase($name);$cmd=$connection.CreateCommand();$cmd.CommandText='CREATE TABLE dbo.LichTruongState(id int PRIMARY KEY, data nvarchar(max) NOT NULL); INSERT INTO dbo.LichTruongState(id,data) VALUES(1,N''{"term":"legacy"}'')';$cmd.ExecuteNonQuery() | Out-Null
    [IO.File]::WriteAllText((Join-Path $PWD 'build/test-db-name.txt'),$name)
    $lines=Get-Content -Encoding UTF8 .env | ForEach-Object { if ($_ -match '^\s*DB_NAME\s*=') { 'DB_NAME='+$name } else { $_ } }
    [IO.File]::WriteAllLines((Join-Path $PWD 'build/test-auth.env'),[string[]]$lines,[Text.UTF8Encoding]::new($false))
    'Temporary test database created.'
  } else {
    $name=[IO.File]::ReadAllText((Join-Path $PWD 'build/test-db-name.txt')).Trim()
    if($name -notmatch '^LichTruongTest_[0-9a-f]{32}$') { throw 'Invalid temporary database name.' }
    $cmd.CommandText="ALTER DATABASE [$name] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [$name]";$cmd.ExecuteNonQuery() | Out-Null
    Remove-Item -LiteralPath 'build/test-db-name.txt','build/test-auth.env'
    'Temporary test database removed.'
  }
} finally {$connection.Close()}
