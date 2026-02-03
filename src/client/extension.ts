import * as vscode from 'vscode';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';

interface TranscriptionMessage {
    type: 'partial' | 'final' | 'vad_stopped' | 'error' | 'ready' | 'connected';
    text?: string;
    error?: string;
}

enum RecordingState {
    Idle = 'idle',
    Connecting = 'connecting',
    Recording = 'recording',
    Transcribing = 'transcribing',
}

let pythonProcess: ChildProcess | null = null;
let statusBarItem: vscode.StatusBarItem;
let outputChannel: vscode.OutputChannel;
let recordingState: RecordingState = RecordingState.Idle;
let currentTranscription = '';
let transcriptionBuffer = '';
let recordingStartTime: number | undefined;
let recordingTimerInterval: NodeJS.Timeout | undefined;

export function activate(context: vscode.ExtensionContext) {
    outputChannel = vscode.window.createOutputChannel('ECodeWhisper');
    outputChannel.appendLine('ECodeWhisper activating...');
    
    statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right,
        100
    );
    statusBarItem.command = 'ecodewhisper.toggleRecording';
    updateStatusBar();
    statusBarItem.show();

    const toggleCommand = vscode.commands.registerCommand(
        'ecodewhisper.toggleRecording',
        () => toggleRecording(context)
    );

    const cancelCommand = vscode.commands.registerCommand(
        'ecodewhisper.cancelRecording',
        () => cancelRecording()
    );

    context.subscriptions.push(toggleCommand, cancelCommand, statusBarItem, outputChannel);

    vscode.commands.executeCommand('setContext', 'ecodewhisper.isRecording', false);
    
    outputChannel.appendLine('ECodeWhisper activated successfully!');
    outputChannel.appendLine(`Extension path: ${context.extensionPath}`);
}

function getConfig() {
    const config = vscode.workspace.getConfiguration('ecodewhisper');
    return {
        pythonPath: config.get<string>('pythonPath') || 'python3',
        whisperEndpoint: config.get<string>('whisperEndpoint') || 'http://localhost:4445/v1/audio/transcriptions',
        model: config.get<string>('model') || 'small',
        language: config.get<string>('language') || 'en',
        vadSilenceThreshold: config.get<number>('vadSilenceThreshold') || 1.5,
        vadThreshold: config.get<number>('vadThreshold') || 0.5,
        sampleRate: config.get<number>('sampleRate') || 16000,
        autoInsert: config.get<boolean>('autoInsert') ?? true,
        showPartialResults: config.get<boolean>('showPartialResults') ?? true,
        minRecordingTime: config.get<number>('minRecordingTime') || 1.0,
    };
}

function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? '0' + secs : secs}`;
}

function updateStatusBar() {
    switch (recordingState) {
        case RecordingState.Idle:
            statusBarItem.text = '$(mic) ECodeWhisper';
            statusBarItem.tooltip = 'Click to start recording (Ctrl+Shift+E)';
            statusBarItem.backgroundColor = undefined;
            break;
        case RecordingState.Connecting:
            statusBarItem.text = '$(loading~spin) Connecting...';
            statusBarItem.tooltip = 'Connecting to microphone';
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
            break;
        case RecordingState.Recording:
            if (recordingStartTime) {
                const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
                statusBarItem.text = `$(stop) ${formatTime(elapsed)}`;
                statusBarItem.tooltip = 'Recording - Click or press Ctrl+Shift+E to stop';
            } else {
                statusBarItem.text = '$(record) Recording...';
                statusBarItem.tooltip = 'Recording - Click or press Ctrl+Shift+E to stop';
            }
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
            break;
        case RecordingState.Transcribing:
            statusBarItem.text = '$(loading~spin) Transcribing...';
            statusBarItem.tooltip = 'Processing transcription';
            statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
            break;
    }
}

function setRecordingState(state: RecordingState) {
    outputChannel.appendLine(`State change: ${recordingState} -> ${state}`);
    recordingState = state;
    updateStatusBar();
    vscode.commands.executeCommand(
        'setContext',
        'ecodewhisper.isRecording',
        state === RecordingState.Recording
    );
}

async function toggleRecording(context: vscode.ExtensionContext) {
    outputChannel.appendLine(`Toggle recording called. Current state: ${recordingState}`);
    
    if (recordingState === RecordingState.Transcribing) {
        outputChannel.appendLine('Cannot toggle: transcription in progress');
        vscode.window.showInformationMessage('ECodeWhisper: Please wait for transcription to complete.');
        return;
    }
    
    if (recordingState === RecordingState.Idle) {
        await startRecording(context);
    } else if (recordingState === RecordingState.Recording) {
        await stopRecording();
    }
}

async function startRecording(context: vscode.ExtensionContext) {
    const config = getConfig();
    
    setRecordingState(RecordingState.Connecting);
    currentTranscription = '';
    transcriptionBuffer = '';
    recordingStartTime = undefined;

    const pythonScript = path.join(context.extensionPath, 'src', 'server', 'python', 'codewhisper.py');
    
    outputChannel.appendLine(`Python script path: ${pythonScript}`);
    outputChannel.appendLine(`Python path: ${config.pythonPath}`);
    
    const args = [
        pythonScript,
        '--endpoint', config.whisperEndpoint,
        '--model', config.model,
        '--language', config.language,
        '--vad-silence', config.vadSilenceThreshold.toString(),
        '--vad-threshold', config.vadThreshold.toString(),
        '--sample-rate', config.sampleRate.toString(),
        '--min-recording', config.minRecordingTime.toString(),
    ];

    outputChannel.appendLine(`Starting: ${config.pythonPath} ${args.join(' ')}`);

    try {
        pythonProcess = spawn(config.pythonPath, args, {
            cwd: context.extensionPath,
            env: { ...process.env, PYTHONUNBUFFERED: '1' },
        });

        pythonProcess.stdout?.on('data', (data: Buffer) => {
            const lines = data.toString().split('\n').filter(l => l.trim());
            for (const line of lines) {
                handlePythonMessage(line, config);
            }
        });

        pythonProcess.stderr?.on('data', (data: Buffer) => {
            const text = data.toString().trim();
            outputChannel.appendLine(`[stderr] ${text}`);
            // Show critical errors to user
            if (text.includes('Error') || text.includes('error') || text.includes('Traceback')) {
                outputChannel.show(true);
            }
        });

        pythonProcess.on('error', (err) => {
            outputChannel.appendLine(`Process error: ${err.message}`);
            outputChannel.show(true);
            vscode.window.showErrorMessage(`ECodeWhisper: Failed to start Python - ${err.message}`);
            cleanupRecording();
            setRecordingState(RecordingState.Idle);
        });

        pythonProcess.on('close', (code) => {
            outputChannel.appendLine(`Python process exited with code ${code}`);
            cleanupRecording();
            
            if (recordingState !== RecordingState.Idle) {
                finishTranscription(config);
            }
        });

    } catch (err) {
        outputChannel.appendLine(`Error starting process: ${err}`);
        outputChannel.show(true);
        vscode.window.showErrorMessage('ECodeWhisper: Failed to start recording');
        cleanupRecording();
        setRecordingState(RecordingState.Idle);
    }
}

function handlePythonMessage(line: string, config: ReturnType<typeof getConfig>) {
    try {
        const msg: TranscriptionMessage = JSON.parse(line);
        outputChannel.appendLine(`Message: ${JSON.stringify(msg)}`);

        switch (msg.type) {
            case 'connected':
                outputChannel.appendLine('Audio device connected');
                break;
                
            case 'ready':
                setRecordingState(RecordingState.Recording);
                recordingStartTime = Date.now();
                // Start the recording timer
                if (recordingTimerInterval) {
                    clearInterval(recordingTimerInterval);
                }
                recordingTimerInterval = setInterval(updateStatusBar, 1000);
                vscode.window.setStatusBarMessage('🎤 Recording... Speak now!', 3000);
                break;

            case 'partial':
                if (msg.text && config.showPartialResults) {
                    transcriptionBuffer = msg.text;
                    showPartialTranscription(transcriptionBuffer);
                }
                break;

            case 'final':
                if (msg.text) {
                    currentTranscription = msg.text;
                    transcriptionBuffer = '';
                    outputChannel.appendLine(`Final text received: ${msg.text}`);
                }
                break;

            case 'vad_stopped':
                outputChannel.appendLine('VAD detected silence, stopping...');
                setRecordingState(RecordingState.Transcribing);
                cleanupRecording();
                break;

            case 'error':
                outputChannel.appendLine(`Error from Python: ${msg.error}`);
                outputChannel.show(true);
                vscode.window.showErrorMessage(`ECodeWhisper: ${msg.error}`);
                cleanupRecording();
                setRecordingState(RecordingState.Idle);
                break;
        }
    } catch {
        // Non-JSON output, log it
        if (line.trim()) {
            outputChannel.appendLine(`[log] ${line}`);
        }
    }
}

function showPartialTranscription(text: string) {
    vscode.window.setStatusBarMessage(`📝 ${text.slice(-50)}...`, 2000);
}

function cleanupRecording() {
    if (recordingTimerInterval) {
        clearInterval(recordingTimerInterval);
        recordingTimerInterval = undefined;
    }
    pythonProcess = null;
}

async function stopRecording() {
    outputChannel.appendLine('Manual stop requested');
    if (pythonProcess) {
        setRecordingState(RecordingState.Transcribing);
        
        // Send STOP command via stdin
        pythonProcess.stdin?.write('STOP\n');
        outputChannel.appendLine('Sent STOP command');
        
        // Give it time to finish gracefully, then force kill
        setTimeout(() => {
            if (pythonProcess && !pythonProcess.killed) {
                outputChannel.appendLine('Force killing process');
                pythonProcess.kill('SIGINT');
            }
        }, 3000);
    }
}

function cancelRecording() {
    outputChannel.appendLine('Recording cancelled by user');
    if (pythonProcess) {
        pythonProcess.kill('SIGKILL');
    }
    cleanupRecording();
    currentTranscription = '';
    transcriptionBuffer = '';
    setRecordingState(RecordingState.Idle);
    vscode.window.setStatusBarMessage('Recording cancelled', 2000);
}

async function finishTranscription(config: ReturnType<typeof getConfig>) {
    const text = currentTranscription.trim() || transcriptionBuffer.trim();
    
    setRecordingState(RecordingState.Idle);
    recordingStartTime = undefined;

    if (!text) {
        vscode.window.setStatusBarMessage('No speech detected', 2000);
        outputChannel.appendLine('No transcription text to insert');
        return;
    }

    outputChannel.appendLine(`Final transcription: ${text}`);

    // Copy to clipboard
    await vscode.env.clipboard.writeText(text);

    if (config.autoInsert) {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            await editor.edit((editBuilder) => {
                editBuilder.insert(editor.selection.active, text);
            });
            vscode.window.setStatusBarMessage(`✅ Inserted: "${text.slice(0, 30)}${text.length > 30 ? '...' : ''}"`, 3000);
        } else {
            vscode.window.setStatusBarMessage(`📋 Copied: "${text.slice(0, 30)}${text.length > 30 ? '...' : ''}"`, 3000);
        }
    } else {
        vscode.window.setStatusBarMessage(`📋 Copied to clipboard`, 3000);
    }
}

export function deactivate() {
    outputChannel.appendLine('ECodeWhisper deactivating...');
    if (pythonProcess) {
        pythonProcess.kill('SIGKILL');
        pythonProcess = null;
    }
    cleanupRecording();
}
