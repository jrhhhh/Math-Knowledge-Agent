(() => {
  const dialog = document.getElementById('obsidianVault');
  const form = dialog.querySelector('form');
  const status = dialog.querySelector('[role="status"]');
  const submit = form.querySelector('[type="submit"]');
  const options = [...form.querySelectorAll('input')];
  const close = dialog.querySelector('[data-close-vault]');
  let pending = false;
  let opener;

  document.querySelectorAll('[data-open-vault]').forEach(button => {
    button.addEventListener('click', () => {
      opener = button;
      if (!pending) status.textContent = '';
      dialog.showModal();
    });
  });
  close.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => opener?.focus());

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (pending) return;
    if (!options.some(option => option.checked)) {
      status.textContent = '请至少选择一类内容。';
      options[0].focus();
      return;
    }
    const query = new URLSearchParams(options.map(option => [option.name, String(option.checked)]));
    pending = true;
    submit.disabled = true;
    options.forEach(option => { option.disabled = true; });
    status.textContent = '正在打包知识库…';
    try {
      const response = await fetch(`${API}/obsidian/vault?${query}`);
      if (!response.ok || !response.headers.get('content-type')?.includes('application/zip')) {
        throw new Error('Vault download failed');
      }
      const url = URL.createObjectURL(await response.blob());
      const download = document.createElement('a');
      download.href = url;
      download.download = 'Math-Agent-Obsidian.zip';
      document.body.append(download);
      download.click();
      download.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      status.textContent = '下载已发起。解压后在 Obsidian 中打开文件夹，从「知识库索引」开始。';
    } catch {
      status.textContent = '下载失败，请检查 Math-Agent 服务连接后重试。';
    } finally {
      pending = false;
      submit.disabled = false;
      options.forEach(option => { option.disabled = false; });
    }
  });
})();
