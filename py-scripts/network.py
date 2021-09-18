import telnetlib
import time
import paramiko


class Network:
    def __init__(self, ip, user, pswd):
        self.ip = ip
        self.user = user
        self.pswd = pswd

    def telnet_func(self, cmd=[]):
        cmd = 'b"' + str(cmd) + '\n'
        tn = telnetlib.Telnet(self.ip)
        tn.read_until(b"Login: ")
        tn.write(self.user.encode("ascii") + b"\n")
        tn.read_until(b"Password: ")
        tn.write(self.pswd.encode('ascii') + b"\n")
        print("successfully connected to %s" % self.ip)
        tn.write(b"sh\n")
        for i in cmd:
            tn.write(i)
        time.sleep(2)
        output = tn.read_very_eager()
        return output

    def ssh_func(self, cmd):
        ssh = paramiko.SSHClient()  # creating shh client object we use this object to connect to router
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # automatically adds the missing host key
        ssh.connect(self.ip, port=22, username=self.user, password=self.pswd, banner_timeout=600)
        stdin, stdout, stderr = ssh.exec_command(str(cmd))
        output = stdout.readlines()
        ssh.close()
        time.sleep(1)
        return output
