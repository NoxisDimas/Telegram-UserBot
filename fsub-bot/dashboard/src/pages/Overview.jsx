import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Users, FileText, Radio, Clock, Plus, Megaphone, ArrowRight } from 'lucide-react';
import api from '../api/client';
import StatCard from '../components/StatCard';
import { PageLoader } from '../components/LoadingSpinner';
import Badge from '../components/Badge';

export default function Overview() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchStats(); }, []);

  const fetchStats = async () => {
    try { const res = await api.get('/stats'); setStats(res.data); }
    catch (err) { console.error('Failed to fetch stats:', err); }
    finally { setLoading(false); }
  };

  if (loading) return <PageLoader />;

  const statCards = [
    { icon: Users, title: 'Total Users', value: stats?.total_users?.toLocaleString() ?? '0', subtitle: 'Registered bot users' },
    { icon: FileText, title: 'Total Content', value: stats?.total_content?.toLocaleString() ?? '0', subtitle: 'Uploaded media items' },
    { icon: Radio, title: 'Active Channels', value: stats?.active_channels?.toLocaleString() ?? '0', subtitle: 'FSUB channels active' },
    { icon: Clock, title: 'Pending Jobs', value: stats?.pending_jobs?.toLocaleString() ?? '0', subtitle: 'Queued background tasks' },
  ];

  const quickActions = [
    { to: '/fsub', icon: Plus, title: 'Add Channel', desc: 'Add new FSUB channel' },
    { to: '/broadcast', icon: Megaphone, title: 'Broadcast', desc: 'Send message to all users' },
    { to: '/content', icon: FileText, title: 'Manage Content', desc: 'View & manage bot content' },
  ];

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary tracking-tight">Dashboard Overview</h1>
        <p className="text-sm text-text-muted mt-1.5">Welcome back! Here's what's happening with your bot.</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        {statCards.map((card) => (
          <StatCard key={card.title} {...card} />
        ))}
      </div>

      {/* Two-Column Section */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* Recent Content — 3/5 */}
        <div className="lg:col-span-3 card overflow-hidden flex flex-col">
          <div className="flex items-center justify-between px-6 py-5 border-b border-border">
            <h2 className="text-sm font-semibold text-text-primary">Recent Content</h2>
            <Link to="/content" className="text-xs text-neon hover:text-neon-dim font-medium flex items-center gap-1 transition-colors">
              View all <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="flex-1">
            {stats?.recent_contents?.length > 0 ? (
              <div className="divide-y divide-border/50">
                {stats.recent_contents.map((content) => (
                  <div key={content.content_id} className="flex items-center gap-4 px-6 py-4 hover:bg-bg-card-hover transition-colors">
                    <div className="w-10 h-10 rounded-lg bg-bg-secondary border border-border flex items-center justify-center flex-shrink-0">
                      <FileText className="w-4 h-4 text-text-muted" strokeWidth={1.8} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-text-primary truncate">{content.caption || `${content.content_type} content`}</p>
                      <p className="text-xs text-text-muted mt-1">
                        {content.created_at ? new Date(content.created_at).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}
                        {content.files_count > 0 && ` · ${content.files_count} file${content.files_count > 1 ? 's' : ''}`}
                      </p>
                    </div>
                    <Badge variant={content.content_type === 'VIDEO' ? 'info' : content.content_type === 'PHOTO' ? 'success' : 'neutral'}>
                      {content.content_type}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-20">
                <div className="w-14 h-14 rounded-xl bg-bg-secondary border border-border flex items-center justify-center mb-4">
                  <FileText className="w-7 h-7 text-text-muted" strokeWidth={1.5} />
                </div>
                <p className="text-sm text-text-muted font-medium">No content yet</p>
                <p className="text-xs text-text-muted mt-1">Content will appear here when uploaded</p>
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions — 2/5 */}
        <div className="lg:col-span-2 card overflow-hidden flex flex-col">
          <div className="px-6 py-5 border-b border-border">
            <h2 className="text-sm font-semibold text-text-primary">Quick Actions</h2>
          </div>
          <div className="flex-1 p-5 space-y-3">
            {quickActions.map(({ to, icon: Icon, title, desc }) => (
              <Link key={to} to={to}
                className="flex items-center gap-4 p-4 rounded-xl bg-bg-secondary/50 border border-border hover:border-neon/20 hover:bg-bg-card-hover transition-all duration-200 group">
                <div className="w-11 h-11 rounded-xl bg-neon/8 border border-neon/20 flex items-center justify-center flex-shrink-0 transition-shadow duration-200 group-hover:shadow-[0_0_12px_rgba(57,255,20,0.15)]">
                  <Icon className="w-5 h-5 text-neon" strokeWidth={1.8} />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-text-primary">{title}</p>
                  <p className="text-xs text-text-muted mt-0.5">{desc}</p>
                </div>
                <ArrowRight className="w-4 h-4 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
