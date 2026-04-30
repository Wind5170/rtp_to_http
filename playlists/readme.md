


project/
   ├── playlists/           # 存放所有播放列表文件
   └── multicast_addresses/ # 组播地址数据
            ├── collected/    # 收集的，未去重/未校验
            ├── curated/      # 健康检查后有效的组播地址，已去重、格式统一）
            ├── extracted/    # 提取的
            └── archive/      # 历史版本备份
   └── scripts/             # 处理脚本