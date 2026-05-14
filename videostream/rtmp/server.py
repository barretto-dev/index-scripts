import subprocess
import signal
import sys

#CREATES A RTMP SERVER THAT WILL RECEIVE VIDEO STREAM
#FROM DJI FLY APP

cmd = ["./mediamtx"]

process = subprocess.Popen(cmd)

def stop(sig, frame):
    print("Encerrando servidor RTMP...")
    process.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

print("Servidor RTMP rodando na porta 1935")
print("Use no DJI Fly:")
print("rtmp://IP_DO_SEU_PC/live/stream")

process.wait()
