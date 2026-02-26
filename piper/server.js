const express = require('express');
const { exec, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 5001;
// Change this to the filename of the ONNX model you want Piper to use by default.
// Example: "en_US-hfc_female-medium.onnx"
const DEFAULT_VOICE = "en_US-hfc_female-medium.onnx"; // Default voice model
const MODELS_DIR = path.join(__dirname, 'models');

function getPiperPath() {
    const platform = os.platform();
    const isWSL = fs.existsSync('/proc/version') && fs.readFileSync('/proc/version', 'utf8').includes('Microsoft');
    if (platform === 'win32' || (platform === 'linux' && isWSL)) {
        return 'piper.exe';
    } else {
        // For macOS or other platforms, set to default executable
        return './piper';
    }
}

function getModelPath(fileName) {
    const platform = os.platform();
    const isWSL = fs.existsSync('/proc/version') && fs.readFileSync('/proc/version', 'utf8').includes('Microsoft');
    if (platform === 'win32' || (platform === 'linux' && isWSL)) {
        return `${fileName}`;
    } else {
        // For macOS or other platforms, set to default executable
        return path.join(__dirname,fileName);
    }
}

function getVoicePath(voice) {
    const platform = os.platform();
    const isWSL = fs.existsSync('/proc/version') && fs.readFileSync('/proc/version', 'utf8').includes('Microsoft');
    if (platform === 'win32' || (platform === 'linux' && isWSL)) {
        return path.join("models",voice);
    } else {
        // For macOS or other platforms, set to default executable
        return path.join(MODELS_DIR,voice);
    }
}

// Determine file or model path based on the platform and environment
function getPath(fileName, isModel = false) {
    const platform = os.platform();
    const isWSL = platform === 'linux' && fs.existsSync('/proc/version') && fs.readFileSync('/proc/version', 'utf8').includes('Microsoft');
    let basePath = (platform === 'win32' || isWSL) ? '.' : __dirname;
    basePath = isModel && basePath === '.' ? 'models' : MODELS_DIR;

    if (platform === 'win32' || isWSL) {
        return path.join(basePath, fileName);
    } else {
        return path.join(__dirname, fileName);
    }
}

const PIPER_PATH = getPiperPath();

// Middleware 
app.use(cors());
app.use(express.json());

// Function to get the list of voice models available
function getListOfVoices() {
    return fs.readdirSync(MODELS_DIR).filter(file => file.endsWith('.onnx'));
}

// Function to log the request details to a file
function logToTextFile(text, voice) {
    const logEntry = `${new Date().toISOString()}, ${text}, ${voice}\n`;
    console.log(logEntry)
    fs.appendFileSync('log.txt', logEntry, 'utf8');
}

// Function to generate a random file name
function generateRandomFileName() {
    const randomPart = Math.random().toString(36).substring(2, 15);
    const timestampPart = Date.now().toString(36);
    return randomPart + timestampPart + '.wav';
}

// Function to execute the Piper command with the given input and voice
function runExecutable(input, voice, res) {
    const tempFileName = generateRandomFileName();
    const outputFile = getModelPath(tempFileName);
    const voicePath = getVoicePath(voice);
    logToTextFile(input, voice);
    // Use spawn to reliably capture stdout/stderr and process events.
    const args = ['--model', voicePath, '--output_file', outputFile];
    console.log('spawning piper:', PIPER_PATH, args.join(' '));

    const child = spawn(PIPER_PATH, args, { shell: false });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
        stdout += chunk.toString();
    });

    child.stderr.on('data', (chunk) => {
        stderr += chunk.toString();
    });

    child.on('error', (err) => {
        console.error('piper spawn error:', err);
        res.status(500).send(`Error spawning piper: ${err.toString()}`);
    });

    child.on('close', (code, signal) => {
        if (code !== 0) {
            console.error(`piper exited with code ${code}, signal ${signal}, stderr: ${stderr}, stdout: ${stdout}`);
            const body = `Error generating audio. exit: ${code}\n${stderr || ''}\n${stdout || ''}`;
            res.status(500).send(body);
            return;
        }

        try {
            res.setHeader('Content-Type', 'audio/wav');
            res.setHeader('Content-Disposition', `attachment; filename="${tempFileName}"`);

            const readStream = fs.createReadStream(outputFile);
            readStream.pipe(res);

            // Clean up: remove the temporary file after sending it
            readStream.on('end', () => {
                fs.unlink(outputFile, (err) => {
                    if (err) console.error('Error removing temporary file:', err);
                });
            });
        } catch (e) {
            console.error('Error streaming output file:', e);
            res.status(500).send(`Error streaming output file: ${e}`);
        }
    });

    // write input to child stdin if accepted by the executable
    if (child.stdin.writable) {
        child.stdin.write(input);
        child.stdin.end();
    }
}

app.get('/', (req, res) => {
    res.send('Basic piper TTS server. Use /tts to convert text to speech and /voices to get available voices.');
});

// POST request handler
app.post('/tts', (req, res) => {
    const { text, voice = DEFAULT_VOICE } = req.body;
    const trimmedText = text.trim();

    if (!trimmedText) {
        return res.status(400).send('Error parsing json - text');
    }

    const voices = getListOfVoices();
    const selectedVoice = voices.includes(voice) ? voice : DEFAULT_VOICE;

    runExecutable(trimmedText, selectedVoice, res);
});

// GET request handler
app.get('/tts', (req, res) => {
    const text = req.query.text ? req.query.text.trim() : null;
    let voice = req.query.voice || DEFAULT_VOICE;

    if (!text) {
        return res.status(400).send('Missing Text Parameter.');
    }

    const voices = getListOfVoices();
    if (!voices.includes(voice)) {
        voice = DEFAULT_VOICE;
    }

    runExecutable(text, voice, res);
});

// Get available voices
app.get('/voices', (req, res) => {
    const voices = getListOfVoices();
    res.json(voices);
});

// Start the server (allow binding host via HOST env var; default to 0.0.0.0)
const HOST = process.env.HOST || '0.0.0.0';
app.listen(PORT, HOST, () => {
    console.log(`Server listening on http://${HOST}:${PORT}`);
});
