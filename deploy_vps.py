import paramiko, sys

host = "2800117c654e.vps.myjino.ru"
port = 49268
user = "root"
password = "NPudjvk5c/pq"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, port=port, username=user, password=password, look_for_keys=False, timeout=30)

stdin, stdout, stderr = ssh.exec_command("grep -i 'telegram_bot\|Starting.*bot\|polling\|start_polling\|Bot.*error\|monitor\|monitoring' /root/server.log 2>/dev/null; echo '---done'")
data = stdout.read().decode('utf-8', errors='replace')
sys.stdout.reconfigure(encoding='utf-8')
sys.stdout.write(data)

ssh.close()
