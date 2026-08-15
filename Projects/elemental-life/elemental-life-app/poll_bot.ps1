$TOKEN='8896772547:AAGQlbVFW1zxD4AoB77xMCEtBJkDpk-CA-s'
$CHAT_ID='143293811'
$API = "https://api.telegram.org/bot$TOKEN"
$PROJECT = "C:\Temp\elemental-life\elemental-life-app"
$lastId = 0
while($true) {
    try {
        $r = Invoke-RestMethod -Uri "$API/getUpdates?offset=$($lastId+1)&timeout=10" -Method Get -TimeoutSec 15
        if ($r.ok -and $r.result) {
            foreach ($u in $r.result) {
                $lastId = $u.update_id
                $txt = if ($u.message.text) { $u.message.text } elseif ($u.callback_query.data) { $u.callback_query.data } else { $null }
                if (-not $txt) { continue }
                Write-Host "-> $txt"
                $reply = ""
                $keyboard = $null
                switch -Regex ($txt) {
                    '/start|/help|menu' {
                        $reply = '<b>Elemental Life Bot</b> (v2.3)' + [char]10 + [char]10 + '/status — status' + [char]10 + '/build — build APK' + [char]10 + '/send — send APK' + [char]10 + '/smoke — smoke test' + [char]10 + '/sync — sync + build' + [char]10 + '/run &lt;cmd&gt; — run command'
                        $keyboard = @(@(@{text='🔨 Build';callback_data='build'}),@{text='📤 Send';callback_data='send'},@{text='📊 Status';callback_data='status'}),@(@{text='🧪 Smoke';callback_data='smoke'},@{text='🔄 Sync';callback_data='sync_build'})
                    }
                    '/status|^status$' {
                        $apk = "$PROJECT\android\app\build\outputs\apk\debug\app-debug.apk"
                        $exists = Test-Path $apk
                        $size = if ($exists) { "{0:N1} MB" -f ((Get-Item $apk).Length / 1MB) } else { 'N/A' }
                        $git = try { git -C $PROJECT log --oneline -3 2>&1 | Out-String } catch { 'no git' }
                        $reply = "<b>Status</b>" + [char]10 + "APK: $(if($exists){'✅'}else{'❌'}) $size" + [char]10 + "<pre>$git</pre>"
                    }
                    '/build|^build$' {
                        $reply = "Building..." + [char]10 + $(try { $env:JAVA_HOME='C:\Users\yusya\AppData\Local\jdk-17.0.12+7'; & npm run build 2>&1 | Out-String } catch { "Build failed: $_" })
                    }
                    '/send|^send$' {
                        $apk = "$PROJECT\android\app\build\outputs\apk\debug\app-debug.apk"
                        if (-not (Test-Path $apk)) { $reply = "APK not found" } else {
                            $reply = "Sending..."
                            try {
                                Add-Type -AssemblyName System.Net.Http
                                $c = new-object System.Net.Http.HttpClient
                                $m = new-object System.Net.Http.MultipartFormDataContent
                                $f = [System.IO.FileStream]::new($apk, [System.IO.FileMode]::Open)
                                $fc = new-object System.Net.Http.StreamContent($f)
                                $fc.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('application/vnd.android.package-archive')
                                $m.Add($fc, 'document', 'elemental-life.apk')
                                $m.Add([System.Net.Http.StringContent]::new($CHAT_ID), 'chat_id')
                                $r2 = $c.PostAsync("$API/sendDocument", $m).GetAwaiter().GetResult()
                                $reply = if ($r2.IsSuccessStatusCode) { "APK sent!" } else { "Failed: $($r2.StatusCode)" }
                            } catch { $reply = "Error: $_" }
                        }
                    }
                    '/smoke|^smoke$' {
                        $reply = try { & node "$PROJECT\tests\engine.smoke.test.mjs" 2>&1 | Out-String } catch { "Test error: $_" }
                    }
                    '/sync|^sync_build$' {
                        $reply = "Syncing..." + [char]10 + $(try { & npx cap sync android 2>&1 | Out-String } catch { "Sync error: $_" })
                        $reply += "Building..." + [char]10 + $(try { $env:JAVA_HOME='C:\Users\yusya\AppData\Local\jdk-17.0.12+7'; cd android; ./gradlew assembleDebug --no-daemon 2>&1 | Out-String; cd $PROJECT } catch { "Build error: $_" })
                    }
                    default {
                        if ($txt -match '^/run (.*)') {
                            $cmd = $Matches[1]
                            $reply = try { & cmd /c $cmd 2>&1 | Out-String } catch { "Error: $_" }
                        } else {
                            $reply = "Unknown: $txt"
                        }
                    }
                }
                if ($reply) {
                    $body = @{chat_id=$CHAT_ID; text=$reply.Substring(0, [Math]::Min($reply.Length, 4000)); parse_mode='HTML'}
                    if ($keyboard) { $body.reply_markup = @{inline_keyboard=$keyboard} }
                    Invoke-RestMethod -Uri "$API/sendMessage" -Method Post -ContentType "application/json" -Body ($body | ConvertTo-Json -Depth 3) | Out-Null
                }
                if ($u.callback_query) { Invoke-RestMethod -Uri "$API/answerCallbackQuery" -Method Post -ContentType "application/json" -Body (@{callback_query_id=$u.callback_query.id} | ConvertTo-Json) | Out-Null }
            }
        }
    } catch { Write-Host "err: $_" }
}
