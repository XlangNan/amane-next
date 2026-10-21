# Amane-next

![](https://img.shields.io/badge/License-GPLv3-blue.svg)

基于 [sqzw-x/amane](https://github.com/sqzw-x/amane) v0.22.0 的衍生版本, 面向「网盘 `.strm` 文件 + Emby / Jellyfin」的使用场景: 不动 strm 文件, 在原位置刮削; 处理完成后钉钉通知.

上游的全部功能 (自动监控、多源刮削、目录整理、图片超分、智能体、Web 界面) 都保留. 本项目遵循上游的 GPLv3 协议.

## 与上游的区别

当前版本 0.23.0, 相对上游 0.22.0 共有以下改动.

### 1. 原地整理

网盘 `.strm` 文件一旦移动或改名就会失效. 媒体库的「整理方式」新增第一项「原地」 (排在 移动 / 复制 / 硬链接 / 符号链接 之前):

- 视频文件不移动、不复制、不改名
- NFO、海报、封面写在视频旁边, 文件名与视频相同, 只换扩展名
- 缺少的文件会补写; 不创建子目录, 不生成链接
- 开启后目录模板与链接模板不再生效

库设置新增 `in_place` 字段, 需要一次数据库迁移 (启动时自动执行). 详见 [docs/user/libraries.md](docs/user/libraries.md) 的「原地整理」.

### 2. 钉钉机器人通知

一批刮削 / 整理任务全部完成后, 向钉钉群发送一条汇总: 本次处理影片数、成功数、失败数, 以及前 10 部失败影片及原因.

- 在「设置」→「通知」中配置 Webhook、加签密钥、关键词
- 队列清空且静默一段时间后才发送, 一大批任务只发一条
- 保存配置时自动发一条测试消息
- 设置项说明见 [docs/user/configuration.md](docs/user/configuration.md) 的「通知」

### 3. NFO 写入演员头像

演员刮削拿到头像后, 影片 NFO 的 `<actor>` 里会多写一个 `<thumb>`, 内容是头像的外链地址. 只写 http(s) 外链; amane 本地裁剪生成的头像对外部不可访问, 不会写入.

注意: Emby 是否读取这个字段, 以及能否访问到该外链, 取决于 Emby 的版本和网络. 另外 Emby 需要在媒体库里开启 NFO 读取, 演员信息才会进入 Emby.

### 4. 登录

登录页文案改为「访问密码」, 密码即 `AMANE_TOKEN`; 登录状态保存时间由 30 天延长到 365 天.

### 5. 品牌与版本

- 界面左上角名称改为 Amane-next, 使用新的橙色图标 (与上游蓝色图标区分)
- 版本检查读取 [XlangNan/amane-next](https://github.com/XlangNan/amane-next/releases) 的 Release, 不再检查上游

要让界面提示新版本, 需要在本仓库发布 Release, tag 形如 `v0.24.0`.

## 部署 (Docker)

在源码目录执行:

```bash
docker build -t amane:latest .
```

容器端口 8000, 数据目录 `/data`, 媒体目录挂载到 `/media`. 示例见 [compose.yaml](compose.yaml).

登录密码: 在 `environment` 里加一行 `- AMANE_TOKEN=你的密码`, 登录页输入它即可 (不设置则自动生成, 见数据目录的 `token` 文件). 登录状态保存一年. 多个 amane 实例用同一个 IP 不同端口时, 请设成同一个密码, 否则浏览器里的登录状态会互相覆盖.

## 上游功能

- **自动监控** — 实时监控磁盘文件变化并自动刮削
- **多源择优** — 聚合多个数据源的元数据, 逐字段择优
- **目录管理** — 自定义命名规则, 整理本地文件结构
- **图片增强** — 内置超分工具优化低清海报图
- **智能体** — 自然语言检索片库、批量整理、发起刮削
- **Web 界面** — 海报墙、任务队列、结构化日志、可视化设置

上游文档见 [sqzw-x.github.io/amane](https://sqzw-x.github.io/amane/).

## 参与开发

前置依赖: [uv](https://github.com/astral-sh/uv), [pnpm](https://pnpm.io/), [just](https://github.com/casey/just)

```bash
just setup   # 同步依赖
just dev     # 启动 API 与前端
```

开发入口见 [AGENTS.md](AGENTS.md).
