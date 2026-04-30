import os
import time

def generate_multicast_file():
    """
    根据 channel_list.txt 生成 multicast+日期.txt 文件
    """
    input_file = os.path.join('source', 'channel_list.txt')
    
    # 检查输入文件是否存在
    if not os.path.exists(input_file):
        print(f"错误: 输入文件 {input_file} 不存在")
        return
    
    # 读取输入文件
    channels_by_category = {}
    category_order = []  # 记录分类出现的顺序
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                # 跳过第一行说明行
                if line_num == 1 and '分类,频道名称,分辨率,状态,组播地址' in line:
                    print("跳过第一行说明行")
                    continue
                
                # 分割行数据
                parts = line.split(',')
                if len(parts) != 5:
                    print(f"警告: 第 {line_num} 行格式错误，跳过")
                    continue
                
                category, channel_name, resolution, status, multicast_addr = parts
                
                # 跳过状态不为空的行
                if status and status.strip():
                    print(f"警告: 第 {line_num} 行状态不为空，跳过")
                    continue
                
                # 跳过组播地址为空的行
                if not multicast_addr:
                    print(f"警告: 第 {line_num} 行组播地址为空，跳过")
                    continue
                
                # 构建频道名称
                if resolution and resolution != 'SD':
                    display_name = f"{channel_name}-{resolution}"
                else:
                    display_name = channel_name
                
                # 构建完整的组播地址
                if not multicast_addr.startswith('rtp://'):
                    full_addr = f"rtp://{multicast_addr}"
                else:
                    full_addr = multicast_addr
                
                # 按分类分组
                if category not in channels_by_category:
                    channels_by_category[category] = []
                    category_order.append(category)  # 记录分类出现的顺序
                channels_by_category[category].append((display_name, full_addr))
    except Exception as e:
        print(f"读取文件出错: {e}")
        return
    
    # 生成输出文件名
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    output_dir = 'multicast_generate'
    output_file = os.path.join(output_dir, f'multicast_{timestamp}.txt')
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 写入输出文件
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            # 按原始顺序写入分类
            for category in category_order:
                channels = channels_by_category.get(category, [])
                if channels:
                    # 写入分类标记
                    f.write(f"{category},#genre#\n")
                    # 写入频道列表
                    for display_name, full_addr in channels:
                        f.write(f"{display_name},{full_addr}\n")
                    f.write("\n")
            
            # 添加更新时间分类和时间戳
            f.write("更新时间,#genre#\n")
            update_time = time.strftime('%Y/%m/%d %H:%M')
            f.write(f"{update_time},https://taoiptv.com/time.mp4\n")
        print(f"成功生成文件: {output_file}")
        print(f"共处理 {sum(len(channels) for channels in channels_by_category.values())} 个频道")
        print(f"共 {len(channels_by_category)} 个分类")
    except Exception as e:
        print(f"写入文件出错: {e}")

if __name__ == "__main__":
    generate_multicast_file()
