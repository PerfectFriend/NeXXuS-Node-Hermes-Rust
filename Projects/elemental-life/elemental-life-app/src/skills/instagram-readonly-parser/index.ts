/**
 * Instagram Read-Only Parser Skill
 * 
 * Parses public Instagram posts without login via:
 * 1. oEmbed API (post URL → structured data + image) - PRIMARY
 * 2. Public profile scraping as fallback (may be rate-limited)
 * 3. Image download + perceptual hash (pHash) for deduplication
 * 
 * No authentication required for oEmbed on public posts.
 */

export interface InstagramPost {
  id: string;
  shortcode: string;
  imageUrl: string;
  caption: string;
  likes: number;
  comments: number;
  timestamp: number;
  permalink: string;
  isVideo: boolean;
  isCarousel: boolean;
  carouselImages?: string[];
}

export interface ParsedPost extends InstagramPost {
  localImagePath?: string;
  pHash?: string;
  seed?: string; // SHA-256 of caption for deterministic level generation
}

export interface ParserOptions {
  username?: string;
  postUrls?: string[];
  limit?: number;
  filter?: 'photo' | 'reel' | 'carousel' | 'all';
  downloadImages?: boolean;
  imageDir?: string;
}

export interface ParserResult {
  posts: ParsedPost[];
  errors: string[];
  stats: {
    totalFetched: number;
    photosFiltered: number;
    imagesDownloaded: number;
    duplicatesRemoved: number;
  };
}

// Simple perceptual hash for deduplication (placeholder for production)
export function perceptualHash(imageData: Uint8Array, _size: number = 8): string {
  let hash = 0;
  for (let i = 0; i < Math.min(imageData.length, 256); i++) {
    hash = ((hash << 5) - hash) + imageData[i];
    hash |= 0;
  }
  return hash.toString(16).padStart(8, '0');
}

// SHA-256 for caption → seed (using Web Crypto API)
export async function captionToSeed(caption: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(caption);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

// Fetch post details via oEmbed API (works for public posts without auth)
async function fetchPostOEmbed(permalink: string): Promise<{ imageUrl: string; caption: string; authorName: string } | null> {
  const oembedUrl = `https://graph.facebook.com/v18.0/instagram_oembed?url=${encodeURIComponent(permalink)}&omitscript=true`;
  
  try {
    const response = await fetch(oembedUrl);
    if (response.ok) {
      const data = await response.json();
      return {
        imageUrl: data.thumbnail_url || '',
        caption: data.title || '',
        authorName: data.author_name || '',
      };
    }
  } catch (e) {
    console.warn('oEmbed fetch failed:', e);
  }
  return null;
}

// Parse a single Instagram post URL via oEmbed
export async function parsePostUrl(permalink: string): Promise<ParsedPost | null> {
  // Normalize URL
  const normalized = permalink.replace(/\/$/, '');
  const shortcodeMatch = normalized.match(/\/p\/([A-Za-z0-9_-]+)/);
  const shortcode = shortcodeMatch ? shortcodeMatch[1] : 'unknown';
  
  const oembed = await fetchPostOEmbed(normalized);
  if (!oembed) return null;
  
  const seed = await captionToSeed(oembed.caption || normalized);
  
  return {
    id: shortcode,
    shortcode,
    imageUrl: oembed.imageUrl,
    caption: oembed.caption,
    likes: 0,
    comments: 0,
    timestamp: Date.now(),
    permalink: normalized,
    isVideo: false,
    isCarousel: false,
    seed,
  };
}

// Fetch profile posts via public HTML (fallback - may be blocked)
async function fetchProfilePosts(username: string, limit: number = 20): Promise<InstagramPost[]> {
  const url = `https://www.instagram.com/${username}/?__a=1&__d=dis`;
  
  const response = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'application/json, text/plain, */*',
      'Accept-Language': 'en-US,en;q=0.5',
      'X-Requested-With': 'XMLHttpRequest',
    },
  });
  
  if (!response.ok) {
    // Fallback to HTML scraping
    return fetchProfilePostsHtml(username, limit);
  }
  
  try {
    const data = await response.json();
    
    // Try to extract from GraphQL response
    const edges = data?.user?.edge_owner_to_timeline_media?.edges;
    if (edges && edges.length > 0) {
      return edges.slice(0, limit).map((edge: any) => parseGraphqlPost(edge.node));
    }
  } catch (e) {
    // Fall through to HTML scraping
  }
  
  return fetchProfilePostsHtml(username, limit);
}

// Original HTML scraping as fallback
async function fetchProfilePostsHtml(username: string, limit: number = 20): Promise<InstagramPost[]> {
  const url = `https://www.instagram.com/${username}/`;
  
  const response = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.5',
    },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to fetch profile: ${response.status} ${response.statusText}`);
  }
  
  const html = await response.text();
  
  // Try modern data extraction patterns
  const patterns = [
    /window\.__additionalDataLoaded\([^,]+,\s*({.*?})\);/,
    /window\._sharedData\s*=\s*({.*?});/,
    /<script[^>]*type="application\/json"[^>]*>({.*?})<\/script>/s,
  ];
  
  for (const pattern of patterns) {
    const matches = html.match(pattern);
    if (matches) {
      for (const match of matches) {
        try {
          const jsonStr = match.replace(/^.*?\{/, '{').replace(/\);?$/, '');
          const data = JSON.parse(jsonStr);
          
          // Search for media edges in the data
          const edges = findMediaEdges(data);
          if (edges && edges.length > 0) {
            return edges.slice(0, limit).map((edge: any) => parseGraphqlPost(edge.node));
          }
        } catch (e) {
          // Continue to next pattern
        }
      }
    }
  }
  
  // If all patterns fail, return empty array instead of throwing
  console.warn(`Could not extract posts from ${username} - Instagram may have changed their layout`);
  return [];
}

function findMediaEdges(obj: any): any[] | null {
  if (!obj || typeof obj !== 'object') return null;
  
  // Check common paths
  if (obj.graphql?.user?.edge_owner_to_timeline_media?.edges) {
    return obj.graphql.user.edge_owner_to_timeline_media.edges;
  }
  if (obj.data?.user?.edge_owner_to_timeline_media?.edges) {
    return obj.data.user.edge_owner_to_timeline_media.edges;
  }
  if (obj.user?.edge_owner_to_timeline_media?.edges) {
    return obj.user.edge_owner_to_timeline_media.edges;
  }
  
  // Recursively search
  for (const key of Object.keys(obj)) {
    const result = findMediaEdges(obj[key]);
    if (result) return result;
  }
  return null;
}

function parseGraphqlPost(node: any): InstagramPost {
  const caption = node.edge_media_to_caption?.edges?.[0]?.node?.text || '';
  const shortcode = node.shortcode;
  const isVideo = node.is_video;
  const isCarousel = node.__typename === 'GraphSidecar';
  
  let imageUrl = node.display_url;
  let carouselImages: string[] = [];
  
  if (isCarousel && node.edge_sidecar_to_children?.edges) {
    carouselImages = node.edge_sidecar_to_children.edges
      .map((edge: any) => edge.node.display_url)
      .filter(Boolean);
    if (carouselImages.length > 0) {
      imageUrl = carouselImages[0];
    }
  }
  
  return {
    id: node.id,
    shortcode,
    imageUrl,
    caption,
    likes: node.edge_liked_by?.count || 0,
    comments: node.edge_media_to_comment?.count || 0,
    timestamp: node.taken_at_timestamp * 1000,
    permalink: `https://www.instagram.com/p/${shortcode}/`,
    isVideo,
    isCarousel,
    carouselImages,
  };
}

// Download image (returns data URL for web, file path for native)
async function downloadImage(url: string): Promise<string> {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  } catch (e) {
    console.warn('Image download failed:', e);
    return url;
  }
}

export class InstagramParser {
  private cache: Map<string, ParsedPost> = new Map();
  
  async parseProfile(options: ParserOptions): Promise<ParserResult> {
    const { username, limit = 20, filter = 'photo', downloadImages = false } = options;
    const errors: string[] = [];
    let imagesDownloaded = 0;
    let duplicatesRemoved = 0;
    const seenHashes = new Set<string>();
    
    if (!username && (!options.postUrls || options.postUrls.length === 0)) {
      errors.push('Either username or postUrls must be provided');
      return { posts: [], errors, stats: { totalFetched: 0, photosFiltered: 0, imagesDownloaded: 0, duplicatesRemoved: 0 } };
    }
    
    const parsedPosts: ParsedPost[] = [];
    
    // Parse specific post URLs via oEmbed (most reliable)
    if (options.postUrls && options.postUrls.length > 0) {
      for (const postUrl of options.postUrls) {
        try {
          const parsed = await parsePostUrl(postUrl);
          if (parsed) {
            parsedPosts.push(parsed);
            this.cache.set(parsed.shortcode, parsed);
          }
        } catch (e) {
          errors.push(`Failed to parse ${postUrl}: ${e}`);
        }
      }
    }
    
    // Parse profile (fallback)
    if (username) {
      try {
        let posts = await fetchProfilePosts(username, limit);
        
        // Filter by type
        if (filter !== 'all') {
          posts = posts.filter(p => {
            if (filter === 'photo') return !p.isVideo && !p.isCarousel;
            if (filter === 'reel') return p.isVideo && !p.isCarousel;
            if (filter === 'carousel') return p.isCarousel;
            return true;
          });
        }
        
        // Process posts
        for (const post of posts) {
          try {
            // Try oEmbed for better data
            const oembed = await fetchPostOEmbed(post.permalink);
            if (oembed && oembed.caption) post.caption = oembed.caption;
            
            const seed = await captionToSeed(post.caption || post.permalink);
            
            let localImagePath: string | undefined;
            let pHash: string | undefined;
            
            if (downloadImages && post.imageUrl) {
              localImagePath = await downloadImage(post.imageUrl);
              // pHash = perceptualHash(imageData); // Would need actual image data
              if (pHash && seenHashes.has(pHash)) {
                duplicatesRemoved++;
                continue;
              }
              if (pHash) seenHashes.add(pHash);
              imagesDownloaded++;
            }
            
            const parsed: ParsedPost = { ...post, localImagePath, pHash, seed };
            parsedPosts.push(parsed);
            this.cache.set(post.shortcode, parsed);
          } catch (e) {
            errors.push(`Failed to process post ${post.shortcode}: ${e}`);
          }
        }
      } catch (e) {
        errors.push(`Profile fetch failed: ${e}`);
      }
    }
    
    return {
      posts: parsedPosts,
      errors,
      stats: {
        totalFetched: parsedPosts.length,
        photosFiltered: 0,
        imagesDownloaded,
        duplicatesRemoved,
      },
    };
  }
  
  getCachedPost(shortcode: string): ParsedPost | undefined {
    return this.cache.get(shortcode);
  }
  
  clearCache(): void {
    this.cache.clear();
  }
}

// Convenience function for one-liner usage
export async function parseInstagramProfile(options: ParserOptions): Promise<ParserResult> {
  const parser = new InstagramParser();
  return parser.parseProfile(options);
}

// Export for level generation
export async function generateLevelFromPost(post: ParsedPost, geometry: 'hex' | 'square' = 'hex', radius: number = 12) {
  const { buildLevelField } = await import('../../engine/engine.ts');
  
  // Use the post's seed for deterministic generation
  // Convert hex string seed to number
  const seedHex = post.seed || 'default';
  const seed = parseInt(seedHex.slice(0, 8), 16) || Date.now();
  
  const levelConfig = {
    id: 999, // Special Instagram-generated level
    label: `IG:${post.shortcode}`,
    waterDensity: 0.2,
    lifeDensity: 0.15,
    earthDensity: 0.1,
    droplets: 10,
  };
  
  const level = buildLevelField(geometry, radius, seed, levelConfig);
  
  return {
    level,
    seed: seedHex, // Return the original hex seed for reference
    sourcePost: {
      shortcode: post.shortcode,
      permalink: post.permalink,
      caption: post.caption?.slice(0, 100),
    },
  };
}