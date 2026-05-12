import express from 'express';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import os from 'os';

const app = express();  
app.use(express.json());

let cameraProcess = null;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ID = "63696D61746563313233";
const PORT = 8080;
const STORAGE_DIR = '/home/drone/INDEX/index_nuc/streams/compressed';

app.post('/api/camera/start', (req, res) => {
  // const { interval } = req.body;

  // Bloqueia execução do processo, por segurança
  if (cameraProcess) {
    return res.status(400).json({ message: "Camera already in use..." });
  }

  // Inicializa script python para gravar frames
  cameraProcess = spawn('python3', ['../scripts/start_transmission.py']);
 
  // Captura os logs do processo
  cameraProcess.stdout.on('data', (data) => console.log(`[RECORDER]: ${data}.`));

  // Limpa processo no encerramento
  cameraProcess.on('close', (data) => {
    console.log(`[RECORDER]: End process.`);
    cameraProcess = null;
  });

  res.status(200).json({"message":"requisição completa"})

});

// Finaliza o processo de gravação dos dados, e armazena os dados num .zip
app.post('/api/camera/stop', (req, res) => {
  // 1. Encerra o script da câmera
  if (!cameraProcess) {
    console.log("[STOP]: Endpoint /api/camera/start está inativo")
    return res.status(404).json({ message: "Processo Inexistente" });
  }

  // 2. Aguarda o processo fechar antes de zipar
  cameraProcess.on('close', () => {
    const zipper = spawn('python3', ['../scripts/stop_transmission.py']);
    let zipperOutput = "";
    let zipperError = "";

  zipper.stdout.on('data', (data) => console.log(`[STOP]: ${data}.`));

  zipper.stderr.on('data', (data) => console.log(`[STOP]: ${data}.`));

    // 3. Aguarda a compressão terminar
    zipper.on('close', (code) => {
      if (code !== 0) {
        return res.status(500).json({ error: "Falha ao compactar.", details: zipperError });
      }

      const match = zipperOutput.match(/stream_[\d_]+_frames\.zip/);
      const filename = match ? match[0] : null;

      res.status(200).json({
        filename: filename,
        downloadUrl: `/api/camera/download/${filename}`
      });
    });
  });

  // 3. Mata o processo (dispara o 'close' acima)
  cameraProcess.kill('SIGTERM');
});

// Rota de Download do arquivo de frames mais recente
app.get('/api/camera/download-latest', (req, res) => {
  const files = fs.readdirSync(STORAGE_DIR)
    .filter(f => f.endsWith('.zip') && f.startsWith('stream_'))
    .sort()
    .reverse();

  if (files.length === 0) {
    return res.status(404).json({ error: 'Nenhum arquivo encontrado' });
  }

  const latestFile = path.join(STORAGE_DIR, files[0]);
  res.download(latestFile);
});

// Limpa os arquivos pesados salvos pela API (vídeos e frames)
app.delete('/api/cleanup', (req, res) => {
  const cleaner = spawn('python3', ['../scripts/cleanup.py']);
  let cleanerOutput = "";
  let cleanerError = "";

  cleaner.stdout?.on('data', (data) => {
    cleanerOutput += data.toString();
  });

  cleaner.stderr?.on('data', (data) => {
    cleanerError += data.toString();
  });

  cleaner.on('close', (code) => {
    if (code !== 0) {
      return res.status(500).json({ error: "Falha ao limpar arquivos.", details: cleanerError });
    }
    res.status(200).json({ message: "Limpeza concluída com sucesso." });
  });
});

// Cria uma rota inicial para iniciar a API
app.get('/', (req, res) => {
  res.send(`API Iniciada na porta ${PORT}`);
});

// Leitura inicial no servidor
app.listen(PORT, () => {
    // 1. Extrai todos os IPs válidos (JavaScript puro)
    const validIps = Object.values(os.networkInterfaces())
        .flat() 
        // Opcional chain (?.) existe no JS moderno, mas adicionei a checagem clássica por segurança
        .filter(iface => iface && iface.family === 'IPv4' && !iface.internal) 
        .map(iface => iface.address); // Sem o "as string"

    // 2. Tenta pegar o segundo IP, se falhar pega o primeiro
    const selectedIp = validIps[1] || validIps[0] || 'Não encontrado';

    // 3. Log final
    console.log(`
===================================================
📸 API EXPRESS
Status: ONLINE
---------------------------------------------------
Acesso Local:   http://localhost:${PORT}
Acesso na Rede: http://${selectedIp}:${PORT}
===================================================
    `);
});
