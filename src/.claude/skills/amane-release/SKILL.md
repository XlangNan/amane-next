---
name: amane-release
description: >-
  Publishes Amane versions: choose semver bump, write CHANGELOG.md, run
  `just bump`, and push the tag so GitHub Actions fill the Release body.
  Use when the user asks to 发版, bump, cut a release, write changelog, or
  run `just bump`.
---

# 发版

## 硬约束

- 发版提交必须用 `just bump patch|minor|major`. 禁止手改 `pyproject.toml` / `uv.lock` 版本, 禁止手打 tag, 禁止直接跑 `uv version`.
- GitHub Release 正文只来自 `CHANGELOG.md` 里与 tag 匹配的 `##` 节. 不要 `gh release create` / `gh release edit` 当常规流程 (workflow 会填).
- 禁止把每条 commit 摊成一条 changelog.

## 流程

```
判定 bump 段 → 起草 CHANGELOG 节 (等人改) → just bump → push 提交和 tag
```

`just bump` 允许工作区里**只有** `CHANGELOG.md` 未提交. 先写 changelog 再 bump, 不要先 bump.

### 1. 版本号判定

用户明示了 patch / minor / major 就用那个. 否则检查上一个 tag 以来的变更, 按 semver 决定:

```
git describe --tags --abbrev=0
git log <tag>..HEAD --format='%s%n%b'
just bump-dry <kind>
```

`bump-dry` 在 changelog 还没写时会失败; 先算出号即可, 不必等 dry-run 通过.

| 条件 | bump |
|------|------|
| `BREAKING CHANGE:` 或 `type!:` | major |
| 至少一条 `feat` (无 breaking) | minor |
| 其余用户可见变更 (通常是 `fix`) | patch |

`docs` / `test` / `ci` / `chore` / `refactor` 单独出现不够发版. 没有用户可见变更就停下来问.

向用户报一次 `x.y.z => a.b.c` 和判定理由.

### 2. 写 CHANGELOG.md

git log 遵循约定式提交, 用来分组和归并. **不要**把自动生成的 changelog 原样发出去: 合并同一主题, 润色成用户能看懂的短句.

在 `CHANGELOG.md` **最上面** (H1 之后) 插入新节. 有内容才输出该组, 按此顺序:

```
## vX.Y.Z

### ✨ 新功能
### 🐛 修复
### ⚡ 性能
### ⚠️ 破坏性变更
```

对应 `feat` / `fix` / `perf` / breaking. 其它 type 默认不上. 同一 issue/PR 下的 feat+docs+test 合成一条.

`🐛 修复` 只收**已发布版本中存在的缺陷**. 缺陷由本区间的功能或改动引入时, 用户从未见过该状态, 修复并入对应条目或删除, 不单列一行.

条目格式:

```
- **短标题** (#13), 一句话
- **短标题** (#27) @someone
```

- 只写重点, 不要限定条件、实现细节、迁移边角、注意小节
- Issue/PR 写成 `#13`, 禁止 `[#13](https://...)` 包裹
- 英文标点: `,` `;` `:` `()`. 不要 `，` `；` `、` `：`
- 社区贡献: PR 作者不是仓库 owner、也不是 bot 时, 条目末尾 `@login`, 并带 PR 号

```
gh repo view --json owner --jq .owner.login
gh pr view N --json number,author,title
```

从 commit subject 的 `(#N)` 或 `Merge pull request #N` 取号.

写好后**停下让用户review**. 未经审阅不要 bump / push.

### 3. bump 与推送

用户确认稿后:

```
just bump <kind>
git push origin HEAD
git push origin vX.Y.Z
```

macOS / Windows workflow 构建安装包时会抽出该节填进 GitHub Release. 不必轮询、不必手动改 Release 正文. 把 Release URL 告诉用户即可.
