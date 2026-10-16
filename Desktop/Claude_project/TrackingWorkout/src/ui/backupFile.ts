import { backupFileName, type BackupFile } from '../db/backup';

/** 공유 시트(모바일)로 보내고, 안 되면 파일 다운로드로 대체한다 */
export async function deliverBackup(
  file: BackupFile,
  now: Date = new Date(),
): Promise<'shared' | 'downloaded' | 'cancelled'> {
  const name = backupFileName(now);
  const blob = new Blob([JSON.stringify(file)], { type: 'application/json' });
  const shareFile = new File([blob], name, { type: 'application/json' });
  if (navigator.canShare?.({ files: [shareFile] })) {
    try {
      await navigator.share({ files: [shareFile], title: name });
      return 'shared';
    } catch (e) {
      if ((e as Error).name === 'AbortError') return 'cancelled';
      // 사용자 제스처가 끊긴 경우 등 — 다운로드로 대체
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return 'downloaded';
}
