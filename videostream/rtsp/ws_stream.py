import asyncio
import subprocess
import websockets
import logging
import signal
import time
import sys
from datetime import datetime

# ─── Configuração de Logging ───────────────────────────────────────────────────

class PreciseFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        ct = datetime.fromtimestamp(record.created)
        return ct.strftime("%Y-%m-%d %H:%M:%S.") + f"{int(record.msecs):03d}"

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(PreciseFormatter("[%(asctime)s] [%(levelname)-8s] %(message)s"))

log = logging.getLogger("stream")
log.setLevel(logging.DEBUG)
log.addHandler(handler)

# ─── Configurações ─────────────────────────────────────────────────────────────

RTSP_URL = "rtsp://192.168.144.25:8554/main.264"
WS_PORT  = 8554
WIDTH    = 1280
HEIGHT   = 720

# Política de reconexão
RECONNECT_DELAY_INITIAL = 2.0   # segundos antes da 1ª tentativa
RECONNECT_DELAY_MAX     = 30.0  # teto do backoff exponencial
RECONNECT_ATTEMPTS_LOG  = 5     # logar warning a cada N tentativas
FFMPEG_STARTUP_TIMEOUT  = 10.0  # segundos para ffmpeg começar a emitir dados
FFMPEG_READ_TIMEOUT     = 15.0  # segundos sem dados antes de considerar travado
CHUNK_SIZE              = 65536

FFMPEG_CMD = [
    "ffmpeg",
    "-loglevel", "warning",          # reduz ruído; trocar por "info" para debug
    "-rtsp_transport", "tcp",
    "-i", RTSP_URL,
    "-f", "mpegts",
    "-codec:v", "mpeg1video",
    "-s", f"{WIDTH}x{HEIGHT}",
    "-b:v", "800k",
    "-bf", "0",
    "-muxdelay", "0.001",
    "pipe:1",
]

# ─── Estado Global ─────────────────────────────────────────────────────────────

clients: set = set()
shutdown_event = asyncio.Event()
stats = {
    "bytes_sent": 0,
    "frames_broadcast": 0,
    "ffmpeg_restarts": 0,
    "start_time": time.monotonic(),
}

# ─── Gerenciamento de Clientes ─────────────────────────────────────────────────

async def broadcast(data: bytes) -> None:
    if not clients:
        return

    dead: set = set()
    results = await asyncio.gather(
        *[c.send(data) for c in clients],
        return_exceptions=True
    )

    for client, result in zip(list(clients), results):
        if isinstance(result, Exception):
            log.warning(f"Erro ao enviar para {client.remote_address}: {result!r} — removendo cliente")
            dead.add(client)

    if dead:
        clients.difference_update(dead)
        log.info(f"{len(dead)} cliente(s) removido(s) por erro. Ativos: {len(clients)}")

    stats["bytes_sent"] += len(data)
    stats["frames_broadcast"] += 1


async def ws_handler(ws) -> None:
    addr = ws.remote_address
    clients.add(ws)
    log.info(f"[WS] Cliente conectado: {addr}  | Total: {len(clients)}")
    try:
        await ws.wait_closed()
    except Exception as exc:
        log.warning(f"[WS] Conexão encerrada com erro ({addr}): {exc!r}")
    finally:
        clients.discard(ws)
        log.info(f"[WS] Cliente desconectado: {addr} | Total: {len(clients)}")


# ─── Leitura do FFmpeg com Watchdog ────────────────────────────────────────────

async def read_ffmpeg_stream(proc: asyncio.subprocess.Process) -> None:
    """
    Lê chunks do stdout do ffmpeg com timeout.
    Lança asyncio.TimeoutError se nenhum dado chegar em FFMPEG_READ_TIMEOUT segundos,
    indicando stream travado.
    """
    first_chunk = True
    while True:
        timeout = FFMPEG_STARTUP_TIMEOUT if first_chunk else FFMPEG_READ_TIMEOUT
        try:
            chunk = await asyncio.wait_for(proc.stdout.read(CHUNK_SIZE), timeout=timeout)
        except asyncio.TimeoutError:
            label = "startup" if first_chunk else "leitura"
            raise asyncio.TimeoutError(
                f"Timeout de {label} ({timeout}s) — nenhum dado recebido do ffmpeg"
            )

        if not chunk:
            raise EOFError("ffmpeg encerrou o stdout (processo finalizado ou RTSP caiu)")

        if first_chunk:
            log.info("Primeiro chunk recebido — stream ativo ✓")
            first_chunk = False

        await broadcast(chunk)


async def terminate_ffmpeg(proc: asyncio.subprocess.Process) -> None:
    """Encerra ffmpeg de forma controlada."""
    if proc.returncode is not None:
        return
    log.debug("Encerrando processo ffmpeg...")
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        log.warning("ffmpeg não respondeu ao SIGTERM — forçando SIGKILL")
        proc.kill()
        await proc.wait()
    log.debug(f"ffmpeg encerrado (returncode={proc.returncode})")


# ─── Loop de Reconexão ─────────────────────────────────────────────────────────

async def ffmpeg_supervisor() -> None:
    delay = RECONNECT_DELAY_INITIAL
    attempt = 0

    while not shutdown_event.is_set():
        attempt += 1
        log.info(f"[FFmpeg] Iniciando processo (tentativa #{attempt}) → {RTSP_URL}")

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *FFMPEG_CMD,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            log.debug(f"[FFmpeg] PID={proc.pid}")
            stats["ffmpeg_restarts"] += (1 if attempt > 1 else 0)

            await read_ffmpeg_stream(proc)

            # Se chegou aqui, stdout fechou limpo (EOF)
            rc = await proc.wait()
            log.warning(f"[FFmpeg] Processo encerrou com returncode={rc}")

        except asyncio.TimeoutError as exc:
            log.error(f"[FFmpeg] {exc}")

        except EOFError as exc:
            log.warning(f"[FFmpeg] {exc}")

        except FileNotFoundError:
            log.critical("[FFmpeg] Executável 'ffmpeg' não encontrado! Verifique o PATH.")
            shutdown_event.set()
            return

        except Exception as exc:
            log.exception(f"[FFmpeg] Erro inesperado: {exc!r}")

        finally:
            if proc:
                # Captura e loga stderr do ffmpeg para diagnóstico
                if proc.stderr:
                    try:
                        err_bytes = await asyncio.wait_for(proc.stderr.read(4096), timeout=2.0)
                        if err_bytes:
                            for line in err_bytes.decode(errors="replace").splitlines():
                                if line.strip():
                                    log.debug(f"[ffmpeg stderr] {line}")
                    except asyncio.TimeoutError:
                        pass
                await terminate_ffmpeg(proc)

        if shutdown_event.is_set():
            break

        if attempt % RECONNECT_ATTEMPTS_LOG == 0:
            elapsed = time.monotonic() - stats["start_time"]
            log.warning(
                f"[FFmpeg] {attempt} tentativas de reconexão. "
                f"Uptime: {elapsed:.0f}s | "
                f"Bytes enviados: {stats['bytes_sent']:,} | "
                f"Restarts: {stats['ffmpeg_restarts']}"
            )

        log.info(f"[FFmpeg] Reconectando em {delay:.1f}s...")
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass  # Timeout esperado — prossegue para próxima tentativa

        # Backoff exponencial com teto
        delay = min(delay * 2, RECONNECT_DELAY_MAX)


# ─── Servidor Principal ────────────────────────────────────────────────────────

async def main() -> None:
    loop = asyncio.get_running_loop()

    def _signal_handler():
        if not shutdown_event.is_set():
            log.info("Sinal de encerramento recebido — finalizando...")
            shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows não suporta add_signal_handler para todos os sinais
            pass

    log.info(f"Servidor WebSocket iniciando em ws://0.0.0.0:{WS_PORT}")
    log.info(f"Fonte RTSP: {RTSP_URL}  |  Resolução: {WIDTH}x{HEIGHT}")

    async with websockets.serve(ws_handler, "0.0.0.0", WS_PORT):
        log.info("WebSocket server pronto ✓")
        await ffmpeg_supervisor()

    log.info(
        f"Servidor encerrado. "
        f"Total enviado: {stats['bytes_sent']:,} bytes | "
        f"Restarts ffmpeg: {stats['ffmpeg_restarts']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
