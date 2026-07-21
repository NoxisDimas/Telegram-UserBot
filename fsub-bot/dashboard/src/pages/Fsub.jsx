import { useState, useEffect } from 'react';
import { Plus, Pencil, Trash2, Power, PowerOff, Loader2, ExternalLink } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../api/client';
import DataTable from '../components/DataTable';
import Modal from '../components/Modal';
import Badge from '../components/Badge';

export default function Fsub() {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editChannel, setEditChannel] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    identifier: '', title: '', username: '', invite_link: '', is_private: false, is_active: true,
  });

  useEffect(() => { fetchChannels(); }, []);

  const fetchChannels = async () => {
    try {
      const res = await api.get('/fsub/');
      setChannels(res.data);
    } catch { toast.error('Failed to load channels'); }
    finally { setLoading(false); }
  };

  const resetForm = () => setForm({ identifier: '', title: '', username: '', invite_link: '', is_private: false, is_active: true });

  const openAdd = () => { resetForm(); setEditChannel(null); setShowAddModal(true); };

  const openEdit = (ch) => {
    setForm({
      channel_id: ch.channel_id, title: ch.title, username: ch.username || '',
      invite_link: ch.invite_link || '', is_private: ch.is_private, is_active: ch.is_active,
    });
    setEditChannel(ch);
    setShowAddModal(true);
  };

  const handleSubmit = async (e) => {
    e?.preventDefault();
    setSubmitting(true);
    try {
      if (editChannel) {
        await api.put(`/fsub/${editChannel.channel_id}`, {
          title: form.title, username: form.username || null,
          invite_link: form.invite_link || null, is_private: form.is_private, is_active: form.is_active,
        });
        toast.success('Channel updated!');
      } else {
        await api.post('/fsub/', {
          identifier: form.identifier,
          invite_link: form.invite_link || null,
          is_active: form.is_active
        });
        toast.success('Channel added!');
      }
      setShowAddModal(false);
      fetchChannels();
    } catch (err) { 
      let msg = 'Operation failed';
      if (err.response?.data?.detail) {
        msg = Array.isArray(err.response.data.detail) ? err.response.data.detail[0].msg : err.response.data.detail;
      }
      toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg)); 
    }
    finally { setSubmitting(false); }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setSubmitting(true);
    try {
      await api.delete(`/fsub/${deleteTarget.channel_id}`);
      toast.success('Channel deleted!');
      setDeleteTarget(null);
      fetchChannels();
    } catch { toast.error('Failed to delete channel'); }
    finally { setSubmitting(false); }
  };

  const toggleActive = async (ch) => {
    try {
      await api.put(`/fsub/${ch.channel_id}`, { is_active: !ch.is_active });
      toast.success(`Channel ${!ch.is_active ? 'activated' : 'deactivated'}`);
      fetchChannels();
    } catch { toast.error('Failed to update channel'); }
  };

  const columns = [
    {
      key: 'title', label: 'Channel',
      render: (r) => (
        <div>
          <p className="font-medium text-text-primary text-sm">{r.title}</p>
          {r.username && <p className="text-xs text-text-muted mt-0.5">@{r.username}</p>}
        </div>
      ),
    },
    {
      key: 'channel_id', label: 'Channel ID',
      render: (r) => <span className="font-mono text-xs text-text-muted">{r.channel_id}</span>,
    },
    {
      key: 'is_private', label: 'Type',
      render: (r) => <Badge variant={r.is_private ? 'warning' : 'info'} dot>{r.is_private ? 'Private' : 'Public'}</Badge>,
    },
    {
      key: 'is_active', label: 'Status',
      render: (r) => <Badge variant={r.is_active ? 'success' : 'danger'} dot>{r.is_active ? 'Active' : 'Inactive'}</Badge>,
    },
    {
      key: 'actions', label: '',
      render: (r) => (
        <div className="flex items-center gap-0.5">
          {r.username && (
            <a href={`https://t.me/${r.username}`} target="_blank" rel="noopener noreferrer"
              className="p-2 rounded-lg text-text-muted hover:text-neon hover:bg-neon/5 transition-colors" title="Open">
              <ExternalLink className="w-4 h-4" />
            </a>
          )}
          <button onClick={(e) => { e.stopPropagation(); toggleActive(r); }}
            className="p-2 rounded-lg text-text-muted hover:text-warning hover:bg-warning/5 transition-colors"
            title={r.is_active ? 'Deactivate' : 'Activate'}>
            {r.is_active ? <PowerOff className="w-4 h-4" /> : <Power className="w-4 h-4" />}
          </button>
          <button onClick={(e) => { e.stopPropagation(); openEdit(r); }}
            className="p-2 rounded-lg text-text-muted hover:text-neon hover:bg-neon/5 transition-colors" title="Edit">
            <Pencil className="w-4 h-4" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); setDeleteTarget(r); }}
            className="p-2 rounded-lg text-text-muted hover:text-danger hover:bg-danger/5 transition-colors" title="Delete">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ),
    },
  ];

  // Toggle switch component
  const Toggle = ({ label, checked, onChange }) => (
    <label className="flex items-center gap-3 cursor-pointer select-none">
      <button type="button" onClick={() => onChange(!checked)}
        className={`relative w-10 h-[22px] rounded-full transition-colors duration-200 ${checked ? 'bg-neon/30' : 'bg-border'}`}>
        <span className={`absolute top-[3px] left-[3px] w-4 h-4 rounded-full transition-all duration-200 ${checked ? 'translate-x-[18px] bg-neon' : 'bg-text-muted'}`} />
      </button>
      <span className="text-sm text-text-secondary">{label}</span>
    </label>
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">FSUB Channels</h1>
          <p className="text-sm text-text-muted mt-1.5">Manage forced subscription channels</p>
        </div>
        <button onClick={openAdd} className="btn-primary">
          <Plus className="w-4 h-4" /> Add Channel
        </button>
      </div>

      <DataTable columns={columns} data={channels} loading={loading}
        emptyMessage="No channels configured yet. Add your first FSUB channel." />

      {/* Add/Edit Modal */}
      <Modal isOpen={showAddModal} onClose={() => setShowAddModal(false)}
        title={editChannel ? 'Edit Channel' : 'Add Channel'}
        footer={
          <>
            <button onClick={() => setShowAddModal(false)} className="btn-secondary">Cancel</button>
            <button onClick={handleSubmit} disabled={submitting} className="btn-primary">
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
              {editChannel ? 'Save Changes' : 'Add Channel'}
            </button>
          </>
        }
      >
        <form onSubmit={handleSubmit} className="space-y-5">
          {!editChannel ? (
            <>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Channel Username / Link / ID <span className="text-danger">*</span>
                </label>
                <input type="text" value={form.identifier}
                  onChange={(e) => setForm({ ...form, identifier: e.target.value })}
                  required placeholder="@channelusername or -1001234567890" className="input-field" />
                <p className="text-xs text-text-muted mt-2">The bot will automatically fetch the channel title and details.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Invite Link <span className="text-text-muted text-xs">(optional for private channels)</span>
                </label>
                <input type="url" value={form.invite_link}
                  onChange={(e) => setForm({ ...form, invite_link: e.target.value })}
                  placeholder="https://t.me/+invitelink" className="input-field" />
              </div>
              <div className="flex items-center gap-8 pt-2">
                <Toggle label="Active" checked={form.is_active}
                  onChange={(v) => setForm({ ...form, is_active: v })} />
              </div>
            </>
          ) : (
            <>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Title <span className="text-danger">*</span>
                </label>
                <input type="text" value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  required placeholder="My Telegram Channel" className="input-field" />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Username <span className="text-text-muted text-xs">(optional)</span>
                </label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted text-sm">@</span>
                  <input type="text" value={form.username}
                    onChange={(e) => setForm({ ...form, username: e.target.value })}
                    placeholder="channelname" className="input-field pl-8" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-2">
                  Invite Link <span className="text-text-muted text-xs">(for private channels)</span>
                </label>
                <input type="url" value={form.invite_link}
                  onChange={(e) => setForm({ ...form, invite_link: e.target.value })}
                  placeholder="https://t.me/+invitelink" className="input-field" />
              </div>
              <div className="flex items-center gap-8 pt-2">
                <Toggle label="Private" checked={form.is_private}
                  onChange={(v) => setForm({ ...form, is_private: v })} />
                <Toggle label="Active" checked={form.is_active}
                  onChange={(v) => setForm({ ...form, is_active: v })} />
              </div>
            </>
          )}
        </form>
      </Modal>

      {/* Delete Modal */}
      <Modal isOpen={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete Channel" size="sm"
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
          Are you sure you want to delete <span className="font-semibold text-text-primary">{deleteTarget?.title}</span>?
          This action cannot be undone.
        </p>
      </Modal>
    </div>
  );
}
