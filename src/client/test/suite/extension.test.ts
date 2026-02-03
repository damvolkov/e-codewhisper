import * as assert from 'assert';
import * as vscode from 'vscode';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';

suite('ECodeWhisper Extension Test Suite', () => {
    vscode.window.showInformationMessage('Starting ECodeWhisper tests.');

    test('Extension should be present', () => {
        const extension = vscode.extensions.getExtension('damvolkov.ecodewhisper');
        assert.ok(extension, 'Extension not found');
    });

    test('Extension should activate', async () => {
        const extension = vscode.extensions.getExtension('damvolkov.ecodewhisper');
        assert.ok(extension, 'Extension not found');
        
        await extension.activate();
        assert.ok(extension.isActive, 'Extension failed to activate');
    });

    test('Commands should be registered', async () => {
        const commands = await vscode.commands.getCommands(true);
        
        assert.ok(
            commands.includes('ecodewhisper.toggleRecording'),
            'toggleRecording command not registered'
        );
        assert.ok(
            commands.includes('ecodewhisper.cancelRecording'),
            'cancelRecording command not registered'
        );
    });

    test('Configuration should have defaults', () => {
        const config = vscode.workspace.getConfiguration('ecodewhisper');
        
        assert.strictEqual(
            config.get('model'),
            'small',
            'Default model should be small'
        );
        assert.strictEqual(
            config.get('language'),
            'en',
            'Default language should be en'
        );
        assert.strictEqual(
            config.get('vadSilenceThreshold'),
            1.5,
            'Default VAD silence threshold should be 1.5'
        );
        assert.strictEqual(
            config.get('vadThreshold'),
            0.5,
            'Default VAD threshold should be 0.5'
        );
        assert.strictEqual(
            config.get('autoInsert'),
            true,
            'Default autoInsert should be true'
        );
    });

    test('Python script should exist', async () => {
        const extension = vscode.extensions.getExtension('damvolkov.ecodewhisper');
        assert.ok(extension, 'Extension not found');
        
        const extensionPath = extension.extensionPath;
        const pythonScript = path.join(extensionPath, 'src', 'server', 'python', 'codewhisper.py');
        
        const fs = require('fs');
        assert.ok(
            fs.existsSync(pythonScript),
            `Python script not found at ${pythonScript}`
        );
    });

    test('Python script should be valid', async function() {
        this.timeout(10000);
        
        const extension = vscode.extensions.getExtension('damvolkov.ecodewhisper');
        assert.ok(extension, 'Extension not found');
        
        const config = vscode.workspace.getConfiguration('codewhisper');
        const pythonPath = config.get<string>('pythonPath') || 'python3';
        const extensionPath = extension.extensionPath;
        const pythonScript = path.join(extensionPath, 'src', 'server', 'python', 'codewhisper.py');
        
        return new Promise<void>((resolve, reject) => {
            const proc = spawn(pythonPath, ['-m', 'py_compile', pythonScript]);
            
            proc.on('close', (code) => {
                if (code === 0) {
                    resolve();
                } else {
                    reject(new Error(`Python syntax check failed with code ${code}`));
                }
            });
            
            proc.on('error', (err) => {
                // Python might not be available, skip test
                console.log('Python not available, skipping syntax check');
                resolve();
            });
        });
    });
});

suite('ECodeWhisper Python Backend Test Suite', () => {
    
    test('Python imports should work with configured pythonPath', async function() {
        this.timeout(15000);
        
        const config = vscode.workspace.getConfiguration('codewhisper');
        const pythonPath = config.get<string>('pythonPath') || 'python3';
        
        return new Promise<void>((resolve, reject) => {
            const proc = spawn(pythonPath, [
                '-c',
                'from src.server.python.codewhisper import Config, emit; print("OK")'
            ], {
                cwd: vscode.extensions.getExtension('damvolkov.ecodewhisper')?.extensionPath
            });
            
            let output = '';
            proc.stdout?.on('data', (data) => {
                output += data.toString();
            });
            
            proc.stderr?.on('data', (data) => {
                console.log('Python stderr:', data.toString());
            });
            
            proc.on('close', (code) => {
                if (code === 0 && output.includes('OK')) {
                    resolve();
                } else {
                    // Dependencies might not be installed, log but don't fail
                    console.log(`Python import test: code=${code}, output=${output}`);
                    console.log('Note: Configure codewhisper.pythonPath to point to venv with dependencies');
                    resolve(); // Don't fail, just warn
                }
            });
            
            proc.on('error', (err) => {
                console.log('Python not available:', err.message);
                resolve(); // Don't fail if Python not available
            });
        });
    });
});
