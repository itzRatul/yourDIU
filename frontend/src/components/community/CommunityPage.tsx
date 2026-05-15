"use client";
import { useState, useEffect } from "react";
import { Heart, MessageCircle, Trash2, Send, Users } from "lucide-react";
import toast from "react-hot-toast";
import { community, type Post } from "@/lib/api";
import { config } from "@/lib/config";
import { mockPosts } from "@/lib/mock";
import { useAuth } from "@/hooks/useAuth";

function timeAgo(iso: string) {
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60)    return `${secs}s ago`;
  if (secs < 3600)  return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

function Avatar({ name }: { name: string }) {
  return (
    <div className="w-9 h-9 rounded-full bg-diu-green/20 flex items-center justify-center flex-shrink-0">
      <span className="text-diu-green text-sm font-bold">{name[0].toUpperCase()}</span>
    </div>
  );
}

export default function CommunityPage() {
  const [posts, setPosts]     = useState<Post[]>([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const { user } = useAuth();

  useEffect(() => {
    if (config.useMock) { setPosts(mockPosts); setLoading(false); return; }
    community.list()
      .then(r => setPosts(r.posts))
      .catch(() => toast.error("Failed to load posts"))
      .finally(() => setLoading(false));
  }, []);

  const handlePost = async () => {
    if (!content.trim() || posting) return;
    setPosting(true);
    try {
      if (config.useMock) {
        const mock: Post = {
          id: Date.now().toString(), user_id: user?.id ?? "",
          content: content.trim(), likes_count: 0, comments_count: 0,
          created_at: new Date().toISOString(),
          author: { full_name: user?.user_metadata?.full_name ?? "You" },
          is_liked: false,
        };
        setPosts(p => [mock, ...p]);
      } else {
        const post = await community.create(content.trim());
        setPosts(p => [post, ...p]);
      }
      setContent("");
    } catch {
      toast.error("Failed to post");
    } finally {
      setPosting(false);
    }
  };

  const handleLike = async (post: Post) => {
    if (config.useMock) {
      setPosts(p => p.map(pp => pp.id === post.id
        ? { ...pp, is_liked: !pp.is_liked, likes_count: pp.is_liked ? pp.likes_count - 1 : pp.likes_count + 1 }
        : pp,
      ));
      return;
    }
    try {
      const res = await community.like(post.id);
      setPosts(p => p.map(pp => pp.id === post.id
        ? { ...pp, is_liked: res.liked, likes_count: res.likes_count }
        : pp,
      ));
    } catch { toast.error("Failed to like"); }
  };

  const handleDelete = async (id: string) => {
    if (!config.useMock) {
      try { await community.delete(id); } catch { toast.error("Failed to delete"); return; }
    }
    setPosts(p => p.filter(pp => pp.id !== id));
    toast.success("Post deleted");
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Users className="text-purple-400" size={22} />
        <h1 className="text-xl font-bold text-diu-text">Community</h1>
      </div>

      {/* Compose */}
      <div className="bg-diu-bg-card border border-diu-border rounded-2xl p-4 mb-6">
        <textarea
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder="Share something with the DIU community..."
          rows={3}
          className="w-full bg-transparent text-sm text-diu-text placeholder-diu-text-dim resize-none focus:outline-none"
        />
        <div className="flex justify-end mt-2">
          <button
            onClick={handlePost}
            disabled={!content.trim() || posting}
            className="flex items-center gap-2 px-4 py-2 bg-purple-500 hover:bg-purple-600 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Send size={14} />
            {posting ? "Posting..." : "Post"}
          </button>
        </div>
      </div>

      {/* Posts */}
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => <div key={i} className="skeleton h-28 w-full" />)}
        </div>
      ) : posts.length === 0 ? (
        <p className="text-center text-diu-text-dim py-12">No posts yet. Be the first!</p>
      ) : (
        <div className="space-y-4">
          {posts.map(post => (
            <div key={post.id} className="bg-diu-bg-card border border-diu-border rounded-2xl p-4 animate-fade-in">
              <div className="flex items-start gap-3">
                <Avatar name={post.author?.full_name ?? "U"} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-diu-text">{post.author?.full_name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-diu-text-dim">{timeAgo(post.created_at)}</span>
                      {post.user_id === user?.id && (
                        <button onClick={() => handleDelete(post.id)} className="text-diu-text-dim hover:text-red-400 transition-colors">
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                  </div>
                  <p className="text-sm text-diu-text mt-1 whitespace-pre-wrap">{post.content}</p>
                  <div className="flex items-center gap-4 mt-3">
                    <button
                      onClick={() => handleLike(post)}
                      className={`flex items-center gap-1.5 text-xs transition-colors ${post.is_liked ? "text-red-400" : "text-diu-text-dim hover:text-red-400"}`}
                    >
                      <Heart size={13} fill={post.is_liked ? "currentColor" : "none"} />
                      {post.likes_count}
                    </button>
                    <span className="flex items-center gap-1.5 text-xs text-diu-text-dim">
                      <MessageCircle size={13} />
                      {post.comments_count}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
