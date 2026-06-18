// Minimal vanilla JS — no build step, no external dependencies.

function statusHtml(m) {
  const extra = (m.progress && m.status === 'processing') ? ' · ' + m.progress : '';
  return `<span class="status status-${m.status}">${m.status}${extra}</span>`;
}

function renderRows(meetings) {
  const body = document.getElementById('meetings-body');
  if (!body) return;
  if (!meetings.length) {
    body.innerHTML = '<tr><td colspan="5" class="muted">No meetings yet. Upload one above.</td></tr>';
    return;
  }
  body.innerHTML = meetings.map(m => `
    <tr>
      <td><a href="/meetings/${m.id}">${escapeHtml(m.title)}</a></td>
      <td><span class="tag">${m.source}</span></td>
      <td>${statusHtml(m)}</td>
      <td class="muted">${(m.created_at || '').replace('T', ' ').slice(0, 19)}</td>
      <td><a class="btn-link" href="/meetings/${m.id}">open →</a></td>
    </tr>`).join('');
}

function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, c => (
    {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]
  ));
}

async function refreshMeetings() {
  try {
    const res = await fetch('/api/meetings');
    if (res.ok) renderRows(await res.json());
  } catch (e) { /* ignore transient errors */ }
}

function initIndexPage() {
  const form = document.getElementById('upload-form');
  const statusEl = document.getElementById('upload-status');
  if (form) {
    form.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const fileInput = document.getElementById('file');
      if (!fileInput.files.length) return;
      const data = new FormData();
      data.append('file', fileInput.files[0]);
      data.append('title', document.getElementById('title').value || '');

      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/meetings');
      document.getElementById('upload-btn').disabled = true;
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          statusEl.textContent = `Uploading… ${pct}%`;
        }
      };
      xhr.onload = () => {
        document.getElementById('upload-btn').disabled = false;
        if (xhr.status === 200) {
          statusEl.textContent = '✅ Uploaded. Processing started — it will appear below.';
          form.reset();
          refreshMeetings();
        } else {
          let msg = xhr.responseText;
          try { msg = JSON.parse(xhr.responseText).detail || msg; } catch (e) {}
          statusEl.textContent = '❌ ' + msg;
        }
      };
      xhr.onerror = () => {
        document.getElementById('upload-btn').disabled = false;
        statusEl.textContent = '❌ Upload failed (network).';
      };
      xhr.send(data);
    });
  }
  refreshMeetings();
  setInterval(refreshMeetings, 4000);
}

async function deleteMeeting(id) {
  if (!confirm('Delete this meeting and its audio? This cannot be undone.')) return;
  const res = await fetch('/api/meetings/' + id, { method: 'DELETE' });
  if (res.ok) {
    window.location.href = '/';
  } else {
    alert('Delete failed.');
  }
}
