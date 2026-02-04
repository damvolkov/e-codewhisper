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
let partialDecorator: vscode.TextEditorDecorationType | undefined;
let lastInsertedRange: vscode.Range | undefined;

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

    // Create decorator for partial transcription preview
    partialDecorator = vscode.window.createTextEditorDecorationType({
        after: {
            color: new vscode.ThemeColor('editorGhostText.foreground'),
            fontStyle: 'italic',
        }
    });

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
        whisperEndpoint: config.get<string>('whisperEndpoint') || 'ws://localhost:4445/v1/audio/transcriptions',
        model: config.get<string>('model') || '',
        language: config.get<string>('language') || 'es',
        vadSilenceThreshold: config.get<number>('vadSilenceThreshold') || 1.5,
        vadThreshold: config.get<number>('vadThreshold') || 0.5,
        sampleRate: config.get<number>('sampleRate') || 16000,
        autoInsert: config.get<boolean>('autoInsert') ?? true,
        showPartialResults: config.get<boolean>('showPartialResults') ?? true,
        minRecordingTime: config.get<number>('minRecordingTime') || 1.0,
        streamingInsert: config.get<boolean>('streamingInsert') ?? true,
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
            statusBarItem.tooltip = 'Connecting to microphone and WebSocket';
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
            statusBarItem.text = '$(loading~spin) Finishing...';
            statusBarItem.tooltip = 'Finishing transcription';
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
    lastInsertedRange = undefined;

    const pythonScript = path.join(context.extensionPath, 'src', 'server', 'python', 'codewhisper.py');
    
    outputChannel.appendLine(`Python script path: ${pythonScript}`);
    outputChannel.appendLine(`Python path: ${config.pythonPath}`);
    outputChannel.appendLine(`WebSocket endpoint: ${config.whisperEndpoint}`);
    
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
                outputChannel.appendLine('WebSocket connected');
                break;
                
            case 'ready':
                setRecordingState(RecordingState.Recording);
                recordingStartTime = Date.now();
                if (recordingTimerInterval) {
                    clearInterval(recordingTimerInterval);
                }
                recordingTimerInterval = setInterval(updateStatusBar, 1000);
                vscode.window.setStatusBarMessage('🎤 Recording... Speak now!', 3000);
                break;

            case 'partial':
                if (msg.text && config.showPartialResults) {
                    transcriptionBuffer = msg.text;
                    if (config.streamingInsert && config.autoInsert) {
                        updateStreamingText(msg.text);
                    } else {
                        showPartialTranscription(msg.text);
                    }
                }
                break;

            case 'final':
                if (msg.text) {
                    currentTranscription = msg.text;
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
        if (line.trim()) {
            outputChannel.appendLine(`[log] ${line}`);
        }
    }
}

async function updateStreamingText(text: string) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        showPartialTranscription(text);
        return;
    }

    // If we have a previous insertion, replace it; otherwise insert at cursor
    await editor.edit((editBuilder) => {
        if (lastInsertedRange) {
            editBuilder.replace(lastInsertedRange, text);
        } else {
            editBuilder.insert(editor.selection.active, text);
        }
    }, { undoStopBefore: !lastInsertedRange, undoStopAfter: false });

    // Calculate the new range of inserted text
    const startPos = lastInsertedRange ? lastInsertedRange.start : editor.selection.active;
    const lines = text.split('\n');
    let endLine = startPos.line + lines.length - 1;
    let endChar = lines.length === 1 
        ? startPos.character + text.length 
        : lines[lines.length - 1].length;
    
    lastInsertedRange = new vscode.Range(startPos, new vscode.Position(endLine, endChar));
    
    // Show status
    const preview = text.length > 40 ? text.slice(-40) + '...' : text;
    vscode.window.setStatusBarMessage(`📝 ${preview}`, 1500);
}

function showPartialTranscription(text: string) {
    const preview = text.length > 50 ? '...' + text.slice(-50) : text;
    vscode.window.setStatusBarMessage(`📝 ${preview}`, 2000);
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
        
        pythonProcess.stdin?.write('STOP\n');
        outputChannel.appendLine('Sent STOP command');
        
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
    
    // Remove any partial text that was inserted
    if (lastInsertedRange) {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            editor.edit((editBuilder) => {
                editBuilder.delete(lastInsertedRange!);
            });
        }
    }
    
    currentTranscription = '';
    transcriptionBuffer = '';
    lastInsertedRange = undefined;
    setRecordingState(RecordingState.Idle);
    vscode.window.setStatusBarMessage('Recording cancelled', 2000);
}

async function finishTranscription(config: ReturnType<typeof getConfig>) {
    const text = currentTranscription.trim() || transcriptionBuffer.trim();
    
    setRecordingState(RecordingState.Idle);
    recordingStartTime = undefined;

    if (!text) {
        // Remove any partial insertions if no final text
        if (lastInsertedRange) {
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                await editor.edit((editBuilder) => {
                    editBuilder.delete(lastInsertedRange!);
                });
            }
        }
        vscode.window.setStatusBarMessage('No speech detected', 2000);
        outputChannel.appendLine('No transcription text to insert');
        lastInsertedRange = undefined;
        return;
    }

    outputChannel.appendLine(`Final transcription: ${text}`);

    // Copy to clipboard
    await vscode.env.clipboard.writeText(text);

    // If streaming insert was used, the text is already there - just finalize
    if (config.streamingInsert && config.autoInsert && lastInsertedRange) {
        // Make sure final text matches what was inserted
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            await editor.edit((editBuilder) => {
                editBuilder.replace(lastInsertedRange!, text);
            }, { undoStopBefore: false, undoStopAfter: true });
        }
        vscode.window.setStatusBarMessage(`✅ "${text.slice(0, 30)}${text.length > 30 ? '...' : ''}"`, 3000);
    } else if (config.autoInsert) {
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
    
    lastInsertedRange = undefined;
}

export function deactivate() {
    outputChannel.appendLine('ECodeWhisper deactivating...');
    if (pythonProcess) {
        pythonProcess.kill('SIGKILL');
        pythonProcess = null;
    }
    cleanupRecording();
    if (partialDecorator) {
        partialDecorator.dispose();
    }
}
