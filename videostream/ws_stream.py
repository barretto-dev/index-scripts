import asyncio
import re
import websockets

## CONNECTS WITH A RTMP SERVER, CONVERT TO MPEG1 AND
## SEND IT TO CLIENT THROUGHT WEBSOCKET

RTMP_URL = "rtmp://localhost/live/stream"
WS_PORT  = 8765   # ⚠️ importante: NÃO use 1935 (porta do RTMP)
WIDTH    = 720
HEIGHT   = 1280
READ_SIZE = 32768
RECONNECT_MIN_DELAY = 1
RECONNECT_MAX_DELAY = 10

FFMPEG_CMD = [
    "ffmpeg",
    "-nostdin",
    "-hide_banner",
    "-nostats",
    "-loglevel", "info",
    "-i", RTMP_URL,              # RTMP input
    "-f", "mpegts",              # container MPEG-TS (JSMpeg)
    "-codec:v", "mpeg1video",    # JSMpeg só suporta MPEG1
    "-b:v", "800k",
    "-bf", "0",                  # baixa latência
    "-muxdelay", "0.001",
    "pipe:1"
]

clients = set()
VIDEO_SIZE_RE = re.compile(r"Video:.*?(\d{2,5})x(\d{2,5})(?:[,\s\[])")

async def broadcast(data):
    if not clients:
        return

    active_clients = tuple(clients)
    results = await asyncio.gather(
        *[client.send(data) for client in active_clients],
        return_exceptions=True,
    )

    for client, result in zip(active_clients, results):
        if isinstance(result, Exception):
            clients.discard(client)

async def handler(ws):
    clients.add(ws)
    print(f"Cliente conectado: {ws.remote_address} | Total: {len(clients)}")
    try:
        await ws.wait_closed()
    finally:
        clients.discard(ws)
        print(f"Cliente desconectado. Total: {len(clients)}")

async def log_ffmpeg_stderr(proc):
    in_input_section = False
    printed_input_size = False

    while True:
        line = await proc.stderr.readline()
        if not line:
            break

        text = line.decode(errors="ignore").rstrip()

        if text.startswith("Input #"):
            in_input_section = True
        elif text.startswith("Output #"):
            in_input_section = False

        if in_input_section and not printed_input_size and "Video:" in text:
            match = VIDEO_SIZE_RE.search(text)
            if match:
                width, height = match.groups()
                print(f"Tamanho da imagem de entrada: {width}x{height}")
                printed_input_size = True

        print(f"ffmpeg: {text}")

async def stop_ffmpeg(proc):
    if proc.returncode is not None:
        return

    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=3)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()

async def ffmpeg_reader():
    reconnect_delay = RECONNECT_MIN_DELAY

    while True:
        proc = None
        stderr_task = None

        try:
            proc = await asyncio.create_subprocess_exec(
                *FFMPEG_CMD,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stderr_task = asyncio.create_task(log_ffmpeg_stderr(proc))
            print("ffmpeg iniciado, lendo stream RTMP...")

            while True:
                chunk = await proc.stdout.read(READ_SIZE)
                if not chunk:
                    break

                reconnect_delay = RECONNECT_MIN_DELAY
                await broadcast(chunk)

            return_code = await proc.wait()
            print(f"ffmpeg encerrou com código {return_code}. Tentando reconectar...")

        except asyncio.CancelledError:
            if proc is not None:
                await stop_ffmpeg(proc)
            raise

        except FileNotFoundError:
            print("ERRO: ffmpeg não encontrado no PATH. Instale o ffmpeg e reinicie.")
            reconnect_delay = RECONNECT_MAX_DELAY

        except Exception as exc:
            print(f"Erro no ffmpeg_reader: {exc!r}. Tentando reconectar...")

        finally:
            if proc is not None:
                await stop_ffmpeg(proc)
            if stderr_task is not None:
                await stderr_task

        print(f"Nova tentativa em {reconnect_delay}s...")
        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, RECONNECT_MAX_DELAY)

async def main():
    print(f"Servidor WebSocket em ws://0.0.0.0:{WS_PORT}")
    async with websockets.serve(
        handler,
        "0.0.0.0",
        WS_PORT,
        max_size=None,
        compression=None,
        ping_interval=20,
        ping_timeout=20,
    ):
        await ffmpeg_reader()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServidor parado.")

