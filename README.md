# 港股市场审核动态周报

一个完全独立的静态网站。网页、二维码和分享长图均属于同一站点，不依赖或跳转到其他周报网站。

## 数据原则

- 港股发行数据：HKEX New Listing Report 官方 Excel。
- 股价数据：港交所主板每日报价官方页面。
- 申请及 PHIP：HKEX AP/PHIP 官方 JSON。
- 境外发行上市备案：证监会备案公示 API 和官方 Excel。
- 关键来源失败或字段无法勾稽时，脚本直接失败，不以估算值补齐。

## 本地预览

```powershell
python scripts/fetch_data.py --as-of 2026-09-11
python -m http.server 8000
```

打开 `http://localhost:8000/`。必须通过 HTTP 预览，直接双击 `index.html` 时浏览器通常不允许读取 `data/report.json`。

## 生成带本站二维码的长图

```powershell
python scripts/generate_poster.py --site-url "https://你的域名/"
```

网页中的“下载本周长图”也会在浏览器内生成同样的 1080×3400 PNG，并把当前网页地址编码为二维码。

## 每周自动更新

项目内置 `.github/workflows/weekly-update.yml`：

- 北京时间每周六 10:30 自动运行；
- 统计周期为前一周周六至周五；
- 抓取和验证数据；
- 生成 `data/report.json`、历史快照和 `poster.png`；
- 自动提交更新并部署 GitHub Pages。

将该目录作为 GitHub 仓库根目录推送后，在仓库 Settings → Pages 中选择 **GitHub Actions** 即可。首次也可在 Actions 页面手动运行并指定截止日期。

## 统计口径

- “IPO / 介绍上市”不含 GEM 转主板项目。
- 募资额按 HKEX New Listing Report 的 `(a)` 与 `(b)` 行合计。
- 首日涨跌幅按上市日官方收市价除以发行价计算。
- “申请版本（第一次呈交）”沿用港交所文件名称，可能包括重新递交。
- 证监会模块仅展示官方表中的状态，不将“已接收”“征求意见”或“补充材料”表述为“完成备案”。

