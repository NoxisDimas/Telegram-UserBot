import { useState, useEffect } from 'react';
import { Trash2, Loader2, FileText, Video, Image, Music, Film, Plus, UploadCloud, Link as LinkIcon } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../api/client';
import DataTable from '../components/DataTable';
import Modal from '../components/Modal';
import Badge from '../components/Badge';

const typeIcons = { VIDEO: Video, PHOTO: Image, DOCUMENT: FileText, AUDIO: Music, ANIMATION: Film };
const typeColors = { VIDEO: 'info', PHOTO: 'success', DOCUMENT: 'neutral', AUDIO: 'warning', ANIMATION: 'info' };

export default function Content() {
  const [contents, setContents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  
  const [showAddModal, setShowAddModal] = useState(false);
  const [addTab, setAddTab] = useState('link'); // 'link' or 'file'
  const [addForm, setAddForm] = useState({ link: '', caption: '', file: null });

  useEffect(() => { fetchContents(); }, []);

  const fetchContents = async () => {
    try { const res = await api.get('/content/'); setContents(res.data); }
    catch { toast.error('Failed to load content'); }
    finally { setLoading(false); }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setSubmitting(true);
    try {
      await api.delete(`/content/${deleteTarget.content_id}`);
      toast.success('Content deleted!');
      setDeleteTarget(null);
      fetchContents();
    } catch { toast.error('Failed to delete content'); }
    finally { setSubmitting(false); }
  };

  const handleAddSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      if (addTab === 'link') {
        if (!addForm.link) { toast.error('Please enter a link'); setSubmitting(false); return; }
        await api.post('/content/from-link', { link: addForm.link, caption: addForm.caption || null });
      } else {
        if (!addForm.file) { toast.error('Please select a file'); setSubmitting(false); return; }
        const formData = new FormData();
        formData.append('file', addForm.file);
        if (addForm.caption) formData.append('caption', addForm.caption);
        await api.post('/content/upload-file', formData, { headers: { 'Content-Type': 'multipart/form-data' }});
      }
      toast.success('Content added successfully!');
      setShowAddModal(false);
      setAddForm({ link: '', caption: '', file: null });
      fetchContents();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add content');
    } finally {
      setSubmitting(false);
    }
  };

  const columns = [
    {
      key: 'content_id', label: 'ID',
      render: (r) => <span className="font-mono text-xs text-text-muted" title={r.content_id}>{r.content_id?.slice(0, 8)}…</span>,
    },
    {
      key: 'content_type', label: 'Type',
      render: (r) => {
        const Icon = typeIcons[r.content_type] || FileText;
        return (
          <div className="flex items-center gap-2">
            <Icon className="w-4 h-4 text-text-muted" strokeWidth={1.8} />
            <Badge variant={typeColors[r.content_type] || 'neutral'}>{r.content_type}</Badge>
          </div>
        );
      },
    },
    {
      key: 'caption', label: 'Caption',
      render: (r) => <p className="max-w-[200px] truncate text-text-secondary text-sm" title={r.caption}>{r.caption || '—'}</p>,
    },
    {
      key: 'files', label: 'Files',
      render: (r) => <span className="text-text-secondary text-sm">{r.files?.length ?? 0}</span>,
    },
    {
      key: 'uploader', label: 'Uploader',
      render: (r) => (
        <div>
          <p className="text-sm text-text-primary">{r.uploader?.first_name || r.uploader?.username || 'Unknown'}</p>
          <p className="text-xs text-text-muted">{r.uploader_id}</p>
        </div>
      ),
    },
    {
      key: 'created_at', label: 'Created',
      render: (r) => <span className="text-text-muted text-xs">{r.created_at ? new Date(r.created_at).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}</span>,
    },
    {
      key: 'actions', label: '',
      render: (r) => (
        <button onClick={(e) => { e.stopPropagation(); setDeleteTarget(r); }}
          className="p-2 rounded-lg text-text-muted hover:text-danger hover:bg-danger/5 transition-colors" title="Delete">
          <Trash2 className="w-4 h-4" />
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">Content Management</h1>
          <p className="text-sm text-text-muted mt-1.5">
            View and manage bot contents
            {!loading && (
              <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-bg-card border border-border text-text-muted">
                {contents.length} items
              </span>
            )}
          </p>
        </div>
        
        <button onClick={() => setShowAddModal(true)} className="btn-primary">
          <Plus className="w-4 h-4" /> Add Content
        </button>
      </div>

      <DataTable columns={columns} data={contents} loading={loading}
        emptyMessage="No content uploaded yet. Content will appear here when users submit via the bot." />

      {/* Delete Modal */}
      <Modal isOpen={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete Content" size="sm"
        footer={
          <>
            <button onClick={() => setDeleteTarget(null)} className="btn-secondary">Cancel</button>
            <button onClick={handleDelete} disabled={submitting} className="btn-danger">
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />} Delete
            </button>
          </>
        }
      >
        <p className="text-sm text-text-secondary">
          Are you sure you want to delete this content?
          <span className="block text-xs text-text-muted mt-1 font-mono">{deleteTarget?.content_id}</span>
          This action cannot be undone.
        </p>
      </Modal>

      {/* Add Content Modal */}
      <Modal isOpen={showAddModal} onClose={() => !submitting && setShowAddModal(false)} title="Add Content" size="md">
        <div className="border-b border-border mb-6 flex gap-4">
          <button 
            type="button" 
            onClick={() => setAddTab('link')} 
            className={`pb-3 text-sm font-medium transition-colors border-b-2 ${addTab === 'link' ? 'border-neon text-neon' : 'border-transparent text-text-muted hover:text-text-primary'}`}
          >
            <div className="flex items-center gap-2"><LinkIcon className="w-4 h-4"/> From Telegram Link</div>
          </button>
          <button 
            type="button" 
            onClick={() => setAddTab('file')} 
            className={`pb-3 text-sm font-medium transition-colors border-b-2 ${addTab === 'file' ? 'border-neon text-neon' : 'border-transparent text-text-muted hover:text-text-primary'}`}
          >
            <div className="flex items-center gap-2"><UploadCloud className="w-4 h-4"/> Upload File</div>
          </button>
        </div>

        <form onSubmit={handleAddSubmit} className="space-y-5">
          {addTab === 'link' && (
            <div>
              <label className="block text-sm text-text-muted mb-2">Telegram Message Link</label>
              <input type="text" placeholder="https://t.me/c/12345/678" className="input-field"
                value={addForm.link} onChange={(e) => setAddForm({ ...addForm, link: e.target.value })} required />
              <p className="text-xs text-text-muted mt-2">Bot must have access to the channel/group to fetch this message.</p>
            </div>
          )}

          {addTab === 'file' && (
            <div>
              <label className="block text-sm text-text-muted mb-2">Select File</label>
              <input type="file" className="block w-full text-sm text-text-secondary
                file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold
                file:bg-neon/10 file:text-neon hover:file:bg-neon/20 cursor-pointer"
                onChange={(e) => setAddForm({ ...addForm, file: e.target.files[0] })} required />
            </div>
          )}

          <div>
            <label className="block text-sm text-text-muted mb-2">Caption (Optional)</label>
            <textarea placeholder="Write a caption..." className="input-field min-h-[80px] resize-y"
              value={addForm.caption} onChange={(e) => setAddForm({ ...addForm, caption: e.target.value })} />
          </div>

          <div className="pt-4 flex justify-end gap-3 border-t border-border mt-6">
            <button type="button" onClick={() => setShowAddModal(false)} className="btn-secondary" disabled={submitting}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />} {addTab === 'link' ? 'Import Content' : 'Upload Content'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
