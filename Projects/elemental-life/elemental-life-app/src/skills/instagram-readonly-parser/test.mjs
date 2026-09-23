
#!/usr/bin/env node
/**
 * Test script for Instagram Read-Only Parser
 * Usage: node --experimental-strip-types test.mjs @nasa --limit=5
 *        node --experimental-strip-types test.mjs --post="https://www.instagram.com/p/ABC123/"
 */

import { parseInstagramProfile } from './index.ts';

async function main() {
  const args = process.argv.slice(2);
  
  // Check for post URL argument
  const postArg = args.find(a => a.startsWith('--post='));
  const postUrls = postArg ? [postArg.replace('--post=', '')] : [];
  
  const usernameArg = args.find(a => a.startsWith('@'));
  const username = usernameArg?.replace('@', '');
  
  const limitArg = args.find(a => a.startsWith('--limit='));
  const limit = limitArg ? parseInt(limitArg.replace('--limit=', '')) : 5;
  
  const filterArg = args.find(a => a.startsWith('--filter='));
  const filter = filterArg?.replace('--filter=', '') || 'photo';
  
  const target = username ? `@${username}` : (postUrls.length ? postUrls.join(', ') : '@nasa');
  console.log(`🔍 Parsing ${target} (limit: ${limit}, filter: ${filter})...`);
  
  const startTime = Date.now();
  const result = await parseInstagramProfile({ 
    username, 
    postUrls,
    limit, 
    filter, 
    downloadImages: false 
  });
  const duration = Date.now() - startTime;
  
  console.log(`\n⏱️  Completed in ${duration}ms`);
  console.log(`📊 Stats:`, result.stats);
  
  if (result.errors.length > 0) {
    console.log(`\n⚠️  Errors:`);
    result.errors.forEach(e => console.log(`  - ${e}`));
  }
  
  console.log(`\n📸 Posts found: ${result.posts.length}`);
  result.posts.forEach((post, i) => {
    console.log(`\n${i + 1}. ${post.shortcode}`);
    console.log(`   📅 ${new Date(post.timestamp).toLocaleString()}`);
    console.log(`   ❤️  ${post.likes} likes, 💬 ${post.comments} comments`);
    console.log(`   🖼️  ${post.isVideo ? 'Video' : post.isCarousel ? 'Carousel' : 'Photo'}`);
    console.log(`   📝 Caption: ${post.caption?.slice(0, 80)}${post.caption?.length > 80 ? '...' : ''}`);
    console.log(`   🔗 ${post.permalink}`);
    console.log(`   🌱 Seed: ${post.seed?.slice(0, 16)}...`);
  });
  
  if (result.posts.length > 0) {
    const firstPost = result.posts[0];
    console.log(`\n🎮 Example level generation:`);
    console.log(`   seed = "${firstPost.seed}"`);
    console.log(`   buildLevelField('hex', 12, seed, { waterDensity: 0.2, ... })`);
  }
}

main().catch(console.error);