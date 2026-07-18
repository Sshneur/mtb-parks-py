import paramiko

host = "2800117c654e.vps.myjino.ru"
port = 49268
user = "root"
password = "aSCbS%9hda8k"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=port, username=user, password=password, timeout=15)

stdin, stdout, stderr = client.exec_command("python3 -c \"with open('/root/mtb-parks-py/static/js/app.js') as f: c=f.read(); print('has click handler:', 'addEventListener.*card' in c or 'card.addEventListener' in c); print('lines:', len(c.split('\\n'))); print('window.location:', 'window.location' in c); print('park-title a:', 'park-title a' in c)\"")
print(stdout.read().decode("utf-8", errors="replace"))

client.close()

client.close()
