% prs_ottawa_brg_detect(1);
% prs_ottawa_brg_detect(2);
% prs_ottawa_brg_detect(3);
% prs_ottawa_brg_detect(4);
% prs_ottawa_brg_detect(5);

function prs_ottawa_brg_detect(state_id)
% mode:
%   0 = xu ly theo state_id, khong save, khong plot
%   1 = xu ly theo state_id va save
%   2 = chon folder -> file -> segment -> plot
%   3 = chon folder -> file -> segment -> plot + save
    mode = 3;   % <-- bien dieu khien duy nhat
    
    if nargin < 1 || isempty(state_id)
        state_id = 1;
    end

    Fs = 42e3;
    segment_time = 1;
    segLen = Fs * segment_time;

    thisDir   = fileparts(mfilename('fullpath'));
    basePath  = thisDir;
    outputDir = fullfile(thisDir, 'rs');

    classFolders = {
        '1_Healthy'
        '2_IF'
        '3_OF'
        '4_BF'
        '5_CF'
    };

    switch mode
        case {0, 1}
            runByState(state_id, classFolders, basePath, outputDir, segLen, Fs, mode);

        case {2, 3}
            runBySelection(classFolders, basePath, outputDir, segLen, Fs, mode);

        otherwise
            error('mode khong hop le. Dung 0, 1, 2 hoac 3.');
    end
end


%% =========================
function runByState(state_id, classFolders, basePath, outputDir, segLen, Fs, mode)
    if state_id < 1 || state_id > numel(classFolders)
        error('state_id khong hop le. Gia tri hop le: 1..5');
    end

    type_fa = classFolders{state_id};
    files = loadOttawaFileList(basePath, type_fa);

    saveFolder = fullfile(outputDir, type_fa);
    if mode == 1 && ~exist(saveFolder, 'dir')
        mkdir(saveFolder);
    end

    fprintf('Dang xu ly thu muc: %s\n', fullfile(basePath, type_fa));

    for k = 1:numel(files)
        [data_results, ~] = analyzeOneFile(files(k).name, basePath, type_fa, segLen, Fs);

        if mode == 1
            baseName = erase(files(k).name, '.mat');
            saveName = ['ft_', baseName, '.mat'];
            savePath = fullfile(saveFolder, saveName);
            save(savePath, 'data_results');
            fprintf('Da luu: %s\n', saveName);
        end
    end
end


%% =========================
function runBySelection(classFolders, basePath, outputDir, segLen, Fs, mode)
    folderIdx = selectFolder(classFolders);
    if isempty(folderIdx)
        return;
    end

    type_fa = classFolders{folderIdx};
    files = loadOttawaFileList(basePath, type_fa);

    fileIdx = selectMatFile(files, type_fa);
    if isempty(fileIdx)
        return;
    end

    fileName = files(fileIdx).name;
    baseName = erase(fileName, '.mat');

    [data_results, fft_cache] = analyzeOneFile(fileName, basePath, type_fa, segLen, Fs);

    if isempty(fft_cache)
        fprintf('File %s khong du du lieu de chia segment.\n', fileName);
        return;
    end

    if mode == 3
        saveFolder = fullfile(outputDir, type_fa);
        if ~exist(saveFolder, 'dir')
            mkdir(saveFolder);
        end

        saveName = ['Ket_qua_', baseName, '.mat'];
        savePath = fullfile(saveFolder, saveName);
        save(savePath, 'data_results');
        fprintf('Da luu: %s\n', saveName);
    end

    segIdx = selectSegmentToPlot(numel(fft_cache), baseName);
    if isempty(segIdx)
        return;
    end

    plotFFTWithPhase( ...
        fft_cache(segIdx).f, ...
        fft_cache(segIdx).P1, ...
        fft_cache(segIdx).topIdx, ...
        fft_cache(segIdx).phase_half, ...
        segIdx, baseName);
end


%% =========================
function [data_results, fft_cache] = analyzeOneFile(fileName, basePath, type_fa, segLen, Fs)
    x_full = loadOttawaSignal(fileName, basePath, type_fa);

    N_total = length(x_full);
    numSeg  = floor(N_total / segLen);

    data_results = struct('sec_th', {}, 'Top_Idx', {}, ...
                          'Freq', {}, 'Amp', {}, 'Phase', {});
    fft_cache = struct('f', {}, 'P1', {}, 'topIdx', {}, 'phase_half', {});
    count_peak = 0;

    for i = 1:numSeg
        idx_start = (i - 1) * segLen + 1;
        idx_end   = i * segLen;
        x_seg     = x_full(idx_start:idx_end);

        L = length(x_seg);
        Y = fft(x_seg);

        P2 = abs(Y / L);
        P1 = P2(1:floor(L/2) + 1);
        P1(2:end-1) = 2 * P1(2:end-1); P1(1) = 0;

        f = Fs * (0:floor(L/2)) / L;
        phase_half = angle(Y(1:floor(L/2) + 1));

        nPeaks = min(10, numel(P1));
        [~, sortedIdx] = sort(P1, 'descend');
        topIdx = sortedIdx(1:nPeaks);

        fft_cache(i).f = f;
        fft_cache(i).P1 = P1;
        fft_cache(i).topIdx = topIdx;
        fft_cache(i).phase_half = phase_half;

        for m = 1:nPeaks
            count_peak = count_peak + 1;
            data_results(count_peak).sec_th = i;
            data_results(count_peak).Top_Idx  = m;
            data_results(count_peak).Freq     = f(topIdx(m));
            data_results(count_peak).Amp      = P1(topIdx(m));
            data_results(count_peak).Phase    = phase_half(topIdx(m));
        end
    end
end


%% =========================
function folderIdx = selectFolder(classFolders)
    [idx, ok] = listdlg( ...
        'PromptString', 'Chon folder can xu ly:', ...
        'SelectionMode', 'single', ...
        'ListString', classFolders);

    if ok
        folderIdx = idx;
    else
        folderIdx = [];
    end
end


%% =========================
function fileIdx = selectMatFile(files, type_fa)
    fileList = {files.name};

    [idx, ok] = listdlg( ...
        'PromptString', sprintf('Chon file .mat trong folder %s:', type_fa), ...
        'SelectionMode', 'single', ...
        'ListString', fileList);

    if ok
        fileIdx = idx;
    else
        fileIdx = [];
    end
end


%% =========================
function segIdx = selectSegmentToPlot(numSeg, baseName)
    listStr = arrayfun(@(x) sprintf('Segment %d', x), 1:numSeg, 'UniformOutput', false);

    [idx, ok] = listdlg( ...
        'PromptString', sprintf('Chon segment can plot - %s', baseName), ...
        'SelectionMode', 'single', ...
        'ListString', listStr);

    if ok
        segIdx = idx;
    else
        segIdx = [];
    end
end


%% =========================
function x = loadOttawaSignal(fileName, basePath, type_fa)
    s = load(fullfile(basePath, type_fa, fileName));
    fn = fieldnames(s);
    all_data = s.(fn{1});
    x = all_data(:, 1);
end


%% =========================
function files = loadOttawaFileList(basePath, type_fa)
    folderPath = fullfile(basePath, type_fa);
    files = dir(fullfile(folderPath, '*.mat'));

    if isempty(files)
        error('Khong tim thay file MAT trong: %s', folderPath);
    end
end


%% =========================
function plotFFTWithPhase(f, P1, topIdx, phase_half, segIdx, baseName)
    figure('Name', sprintf('%s - Segment %d', baseName, segIdx), ...
           'Color', 'w');

    plot(f, P1, 'b-', 'LineWidth', 1);
    hold on;
    plot(f(topIdx), P1(topIdx), 'ro', 'MarkerFaceColor', 'r'); xlim([0 f(end)])

    for m = 1:numel(topIdx)
        idx = topIdx(m);
        label = sprintf('P=%.2f', round(phase_half(idx), 2));

        text(f(idx), P1(idx), ['  ' label], ...
            'FontSize', 9, ...
            'Color', 'k', ...
            'VerticalAlignment', 'bottom', ...
            'Interpreter', 'none');
    end

    xlabel('Frequency (Hz)');
    ylabel('Amplitude');
    baseName_plot = strrep(baseName, '_', '\_');
    title(sprintf('FFT - %s - Segment %d', baseName_plot, segIdx));
    grid on;
    hold off;
end