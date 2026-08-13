import { useState } from 'react';
import { parseInstagramProfile, type ParsedPost } from '../skills/instagram-readonly-parser';
import { generateLevelFromPost } from '../skills/instagram-readonly-parser';

interface InstagramImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLevelGenerated: (level: any, seed: string, sourceInfo: any) => void;
}

export function InstagramImportModal({ isOpen, onClose, onLevelGenerated }: InstagramImportModalProps) {
  const [step, setStep] = useState<'input' | 'results' | 'loading'>('input');
  const [postUrl, setPostUrl] = useState('');
  const [posts, setPosts] = useState<ParsedPost[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedPost, setSelectedPost] = useState<ParsedPost | null>(null);

  const handleImport = async () => {
    if (!postUrl.trim()) {
      setError('Введите ссылку на пост Instagram');
      return;
    }

    setStep('loading');
    setError(null);

    try {
      const result = await parseInstagramProfile({ 
        postUrls: [postUrl.trim()],
        filter: 'all',
        downloadImages: false 
      });

      if (result.errors.length > 0) {
        setError(result.errors[0]);
        setStep('input');
        return;
      }

      if (result.posts.length === 0) {
        setError('Пост не найден или недоступен. Проверьте ссылку.');
        setStep('input');
        return;
      }

      setPosts(result.posts);
      setStep('results');
    } catch (e) {
      setError(`Ошибка: ${e}`);
      setStep('input');
    }
  };

  const handleGenerateLevel = async (post: ParsedPost) => {
    setSelectedPost(post);
    setStep('loading');
    
    try {
      const { level, seed, sourcePost } = await generateLevelFromPost(post, 'hex', 12);
      onLevelGenerated(level, seed, sourcePost);
      onClose();
    } catch (e) {
      setError(`Ошибка генерации: ${e}`);
      setStep('results');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal instagram-import-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>📸 Импорт из Instagram</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {step === 'input' && (
          <div className="modal-body">
            <p className="instruction">Вставьте ссылку на публичный пост Instagram (фото, Reels или карусель):</p>
            
            <div className="input-group">
              <input
                type="text"
                value={postUrl}
                onChange={e => setPostUrl(e.target.value)}
                placeholder="https://www.instagram.com/p/ABC123/"
                className="post-url-input"
                onKeyDown={e => e.key === 'Enter' && handleImport()}
              />
              <button 
                className="btn primary" 
                onClick={handleImport}
                disabled={!postUrl.trim()}
              >
                🔍 Найти пост
              </button>
            </div>

            {error && <div className="error-message">{error}</div>}

            <div className="examples">
              <p>Примеры ссылок:</p>
              <ul>
                <li><code>https://www.instagram.com/p/ABC123/</code> — фото</li>
                <li><code>https://www.instagram.com/reel/ABC123/</code> — Reels</li>
                <li><code>https://www.instagram.com/p/ABC123/?img_index=2</code> — карусель</li>
              </ul>
              <p className="note">🔒 Работает только с <strong>публичными</strong> постами. Приватные аккаунты не поддерживаются.</p>
            </div>
          </div>
        )}

        {step === 'results' && (
          <div className="modal-body">
            <p className="success">✅ Найдено постов: {posts.length}</p>
            
            <div className="posts-list">
              {posts.map((post) => (
                <div key={post.shortcode} className="post-card" onClick={() => handleGenerateLevel(post)}>
                  <div className="post-preview">
                    {post.imageUrl && (
                      <img src={post.imageUrl} alt={`Post ${post.shortcode}`} loading="lazy" />
                    )}
                    <div className="post-type-badge">
                      {post.isVideo ? '🎬 Reel' : post.isCarousel ? '🖼️ Карусель' : '📸 Фото'}
                    </div>
                  </div>
                  <div className="post-info">
                    <div className="post-meta">
                      <span>❤️ {post.likes}</span>
                      <span>💬 {post.comments}</span>
                      <span>📅 {new Date(post.timestamp).toLocaleDateString()}</span>
                    </div>
                    <p className="post-caption">{post.caption?.slice(0, 120) || '(без описания)'}{post.caption?.length > 120 ? '...' : ''}</p>
                    <div className="post-seed">Seed: <code>{post.seed?.slice(0, 16)}...</code></div>
                  </div>
                  <button className="btn generate-btn">🎮 Создать уровень</button>
                </div>
              ))}
            </div>

            <div className="modal-footer">
              <button className="btn secondary" onClick={() => { setStep('input'); setPosts([]); setPostUrl(''); }}>
                ← Назад
              </button>
            </div>
          </div>
        )}

        {step === 'loading' && selectedPost && (
          <div className="modal-body loading">
            <div className="spinner"></div>
            <p>Генерация уровня из поста <code>{selectedPost.shortcode}</code>...</p>
            <p className="hint">Caption → SHA-256 → детерминированная генерация поля</p>
          </div>
        )}
      </div>
    </div>
  );
}