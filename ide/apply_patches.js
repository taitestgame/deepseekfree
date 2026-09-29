/**
 * apply_patches.js
 * Tu dong ap dung cac ban va tinh nang vao thu muc node_modules cua Halyard IDE:
 * 1. Chon thu muc in-browser (bo Win32 dialog loi)
 * 2. Mac dinh duyet toan bo o dia C:\
 * 3. Chan cac skill la, chi doc deepseek-4-1.md trong skills
 * 4. Nut cong tac HACK CO LO, Orchestra tren giao dien
 * 5. Tu dong inject deepseek-4-1.md vao System Prompt va dong bo skill
 */
const fs = require('fs');
const path = require('path');
const os = require('os');

const targetHome = process.env.HALYARD_HOME || path.join(os.homedir(), '.halyard');
const patchesDir = path.join(__dirname, 'patches');

console.log('=================================================================');
console.log('🔧 [APPLY PATCHES] DANG AP DUNG BAN VA VAO HALYARD IDE');
console.log('   📂 Thu muc target: ' + targetHome);
console.log('=================================================================');

const patchList = [
  {
    src: path.join(patchesDir, 'dsh-host-directory-picker-auto', 'index.js'),
    dst: path.join(targetHome, 'node_modules', '@deepseek-ai', 'dsh-host-directory-picker-auto', 'lib', 'index.js'),
    desc: 'In-browser Directory Picker (Khong bi dialog an)'
  },
  {
    src: path.join(patchesDir, 'dsh-host-directory-picker-browse', 'index.js'),
    dst: path.join(targetHome, 'node_modules', '@deepseek-ai', 'dsh-host-directory-picker-browse', 'lib', 'index.js'),
    desc: 'Mac dinh mo o dia C:\\ thay vi User profile'
  },
  {
    src: path.join(patchesDir, 'dsh-tool-skill', 'index.js'),
    dst: path.join(targetHome, 'node_modules', '@deepseek-ai', 'dsh-tool-skill', 'lib', 'index.js'),
    desc: 'Dong bo skill catalog voi cong tac HACK CO LO'
  },
  {
    src: path.join(patchesDir, 'dsh-skill-filesystem', 'index.js'),
    dst: path.join(targetHome, 'node_modules', '@deepseek-ai', 'dsh-skill-filesystem', 'lib', 'index.js'),
    desc: 'Chan skill la tu .agents, chi nap tu .halyard/skills'
  },
  {
    src: path.join(patchesDir, 'plugin-account', 'client.js'),
    dst: path.join(targetHome, 'node_modules', '@tokenharbor', 'halyard', 'plugin', 'account', 'client.js'),
    desc: 'Giao dien Switch HACK CO LO va Orchestra'
  },
  {
    src: path.join(patchesDir, 'plugin-account', 'index.mjs'),
    dst: path.join(targetHome, 'node_modules', '@tokenharbor', 'halyard', 'plugin', 'account', 'index.mjs'),
    desc: 'Tat update banner, inject deepseek-4-1.md va API switch'
  }
];

let applied = 0;
for (const p of patchList) {
  try {
    if (!fs.existsSync(p.src)) {
      console.warn('⚠️ Khong tim thay file patch nguon: ' + p.src);
      continue;
    }
    const dstDir = path.dirname(p.dst);
    if (!fs.existsSync(dstDir)) {
      fs.mkdirSync(dstDir, { recursive: true });
    }
    // Backup ban goc neu chua co .orig
    const orig = p.dst + '.orig';
    if (fs.existsSync(p.dst) && !fs.existsSync(orig)) {
      fs.copyFileSync(p.dst, orig);
    }
    fs.copyFileSync(p.src, p.dst);
    console.log(`✅ [OK] ${p.desc}`);
    applied++;
  } catch (err) {
    console.error(`❌ [LOI] ${p.desc}: ${err.message}`);
  }
}

// Dong bo deepseek-4-1.md, fun_mode.json, settings.yaml, skills
const syncFiles = ['deepseek-4-1.md', 'fun_mode.json', 'settings.yaml'];
for (const f of syncFiles) {
  const sf = path.join(__dirname, f);
  const df = path.join(targetHome, f);
  if (fs.existsSync(sf)) {
    fs.copyFileSync(sf, df);
    console.log(`✅ [SYNC] Da copy file cau hinh: ${f}`);
  }
}

// Copy skills folder
const skillsSrc = path.join(__dirname, 'skills');
const skillsDst = path.join(targetHome, 'skills');
if (fs.existsSync(skillsSrc)) {
  fs.cpSync(skillsSrc, skillsDst, { recursive: true });
  console.log(`✅ [SYNC] Da copy thu muc skills: deepseek-4-1 va hack`);
}

// 6. Tu dong cau hinh Model mac dinh Free vao profile/halyard.patch.yml
const halyardPatchYml = path.join(targetHome, 'node_modules', '@tokenharbor', 'halyard', 'profile', 'halyard.patch.yml');
if (fs.existsSync(halyardPatchYml)) {
  let ymlContent = fs.readFileSync(halyardPatchYml, 'utf8');
  let changed = false;
  if (ymlContent.includes('provider: halyard\n    model: th-orchestra')) {
    ymlContent = ymlContent.replace('provider: halyard\n    model: th-orchestra', 'provider: free\n    model: deepseek-v4-flash:free');
    changed = true;
  }
  if (!ymlContent.includes('deepseek-v4.1-flash:free')) {
    ymlContent = ymlContent.replace(
      '- id: deepseek-v4-flash:free\n            input: [text]',
      '- id: deepseek-v4-flash:free\n            input: [text]\n          - id: deepseek-v4.1-flash:free\n            input: [text]'
    );
    changed = true;
  }
  if (changed) {
    fs.writeFileSync(halyardPatchYml, ymlContent, 'utf8');
    console.log('✅ [PATCH] Da cau hinh profile/halyard.patch.yml: Mac dinh su dung deepseek-v4-flash:free');
  }
}

console.log('=================================================================');
console.log(`🎉 HOAN TAT! Da ap dung thanh cong ${applied}/${patchList.length} ban va vao Halyard.`);
console.log('=================================================================');
