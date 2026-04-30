import os
import re
import argparse

def extract_channel_info(file_path):
    """从文件中提取频道信息"""
    channels = []
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            
            # 跳过空行和注释
            if not line or line.startswith('#'):
                continue
            
            # 处理 m3u 格式
            if '.m3u' in file_path.lower():
                if line.startswith('#EXTINF:'):
                    # 提取频道名（格式：#EXTINF:-1 group-title="分类",频道名）
                    match = re.search(r'group-title="([^"]+)"[^,]*,(.+)', line)
                    if match:
                        category = match.group(1)
                        name = match.group(2).strip()
                        channels.append({"category": category, "name": name})
                continue
            
            # 处理 txt 格式（支持多种列格式）
            parts = line.split(',')
            
            # 4列式：分类,频道名,地址,状态
            if len(parts) >= 4:
                category = parts[0].strip() if parts[0].strip() else "未分类"
                name = parts[1].strip()
                channels.append({"category": category, "name": name})
            
            # 3列式：分类,频道名,地址
            elif len(parts) >= 3:
                category = parts[0].strip() if parts[0].strip() else "未分类"
                name = parts[1].strip()
                channels.append({"category": category, "name": name})
            
            # 2列式或单列：频道名,地址 或 只有频道名
            elif len(parts) >= 2:
                # 检查是否有分类标记
                if '#genre#' in parts[0] or '#genre#' in parts[1]:
                    if '#genre#' in parts[0]:
                        category = parts[0].replace('#genre#', '').strip() or "未分类"
                        name = parts[1].strip()
                    else:
                        category = parts[1].replace('#genre#', '').strip() or "未分类"
                        name = parts[0].strip()
                else:
                    # 默认第一列为频道名，第二列为地址
                    category = "未分类"
                    name = parts[0].strip()
                channels.append({"category": category, "name": name})
            
            # 单列格式
            else:
                # 检查是否有分类标记
                if '#genre#' in line:
                    parts = line.split('#genre#')
                    category = parts[0].strip() if len(parts) > 0 else "未分类"
                    name = parts[1].strip() if len(parts) > 1 else ""
                else:
                    category = "未分类"
                    name = line.strip()
                
                if name:
                    channels.append({"category": category, "name": name})
    
    return channels

def detect_region_isp(filename):
    """从文件名中提取地区和运营商信息"""
    region = "未知"
    isp = "未知"
    
    # 地区列表
    regions = ["北京", "上海", "广东", "江苏", "浙江", "山东", "四川", "湖北", "湖南", 
               "河南", "河北", "陕西", "安徽", "福建", "江西", "云南", "贵州", "广西",
               "山西", "辽宁", "吉林", "黑龙江", "内蒙古", "新疆", "西藏", "青海",
               "甘肃", "宁夏", "海南", "重庆", "天津"]
    
    # 运营商列表
    isps = ["电信", "移动", "联通"]
    
    # 检测运营商
    for i in isps:
        if i in filename:
            isp = i
            break
    
    # 检测地区
    for r in regions:
        if r in filename:
            region = r
            break
    
    return region, isp

def main():
    parser = argparse.ArgumentParser(description='从播放列表文件中提取频道分类和频道名')
    parser.add_argument('input_files', nargs='+', help='输入文件路径（支持多个文件）')
    parser.add_argument('--output', '-o', help='输出文件名（可选，默认为 地区_运营商_channel_categories.txt）')
    args = parser.parse_args()
    
    all_channels = {}
    
    for input_file in args.input_files:
        if not os.path.exists(input_file):
            print(f"警告：文件不存在: {input_file}")
            continue
        
        print(f"正在处理: {input_file}")
        channels = extract_channel_info(input_file)
        
        for channel in channels:
            category = channel["category"]
            name = channel["name"]
            
            if category not in all_channels:
                all_channels[category] = set()
            all_channels[category].add(name)
    
    # 检测地区和运营商
    region, isp = "未知", "未知"
    if args.input_files:
        region, isp = detect_region_isp(args.input_files[0])
    
    # 生成输出文件名
    if args.output:
        output_file = args.output
    else:
        output_file = f"{region}_{isp}_channel_categories.txt"
    
    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        for category in sorted(all_channels.keys()):
            for name in sorted(all_channels[category]):
                f.write(f"{category},{name}\n")
    
    print(f"\n提取完成！")
    print(f"共提取 {len(all_channels)} 个分类，{sum(len(names) for names in all_channels.values())} 个频道")
    print(f"结果已保存到: {output_file}")

if __name__ == '__main__':
    main()