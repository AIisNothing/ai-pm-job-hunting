"""
公开分享版报告生成脚本
基于 v18 HTML 做脱敏处理，输出公开版 HTML + 长图 PNG
"""
import re
import os
import asyncio

INPUT_HTML = "data/产品经理_深度分析_v18.html"
OUTPUT_HTML = "data/产品经理_深度分析_公开版.html"
OUTPUT_PNG = "data/产品经理_深度分析_公开版.png"

# 公司名脱敏映射
COMPANY_MAP = {
    "字节跳动": "某头部短视频/内容平台",
    "今日头条": "某头部短视频/内容平台",
    "小米": "某头部智能硬件公司",
    "京东集团": "某头部电商集团",
    "京东物流": "某头部电商集团(物流)",
    "京东科技集团": "某头部电商集团(科技)",
    "京东世纪贸易有限公司": "某头部电商集团(贸易)",
    "百度": "某头部搜索/AI公司",
    "快手": "某短视频平台",
    "美团": "某本地生活平台",
    "腾讯": "某头部社交/游戏公司",
    "阿里巴巴集团": "某头部电商/云计算集团",
    "阿里巴巴智能信息事业群": "某头部电商集团(智能信息)",
    "阿里云": "某头部云计算公司",
    "滴滴": "某出行平台",
    "小红书": "某生活方式社区",
    "理想汽车": "某新能源车企A",
    "蚂蚁集团": "某金融科技公司",
    "360集团": "某安全/互联网公司",
    "高德地图": "某地图/出行服务公司",
    "高德云图": "某地图服务公司(云图)",
    "高德": "某地图/出行服务公司",
    "汽车之家": "某汽车信息平台",
    "去哪儿网": "某在线旅游平台",
    "去哪儿": "某在线旅游平台",
    "同程旅行": "某在线旅游公司",
    "好未来": "某教育科技公司",
    "聚优猎": "某猎头公司",
    "新石器慧通": "某自动驾驶公司",
    "北京行景科技": "某金融科技公司B",
    "北京万联易达科技": "某中型互联网公司A",
    "万联易达集团": "某中型互联网公司A",
    "英讯伟达": "某中型科技公司",
    "北京千千解科技": "某中型内容公司",
    "北京迅志技术有限公司": "某金融科技公司C",
}

# 免责声明
DISCLAIMER = '''
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 20px;margin:16px 0;font-size:12px;color:#666;line-height:1.8">
⚠️ <b>公开版声明：</b>本报告基于公开招聘信息样本做聚合统计分析，仅用于行业研究和求职趋势参考。不提供原始岗位数据、岗位链接、招聘者信息或可反查单个岗位的明细。公司与岗位相关信息已做聚合、泛化或脱敏处理。结论仅反映特定时间、特定筛选条件下的样本情况，不代表完整市场，也不构成对任何平台、公司或岗位的评价。
</div>
'''

TOP15_REPLACEMENT = '''
<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;padding:16px 20px;margin:12px 0;font-size:13px;line-height:1.8">
<b>🔥 极端高薪岗位画像（已脱敏）</b><br><br>
极端高薪样本（月薪中位数≥100K）共54条，主要特征：<br>
• <b>方向分布：</b>AI/大模型产品、策略产品、商业化/广告为主<br>
• <b>职级类型：</b>总监、负责人、VP、首席产品官<br>
• <b>薪资粗档位：</b>100-150K约30条，150-200K约15条，200K+约9条<br>
• <b>猎头占比：</b>极端高薪样本中猎头岗位占比较高，薪资区间可能偏宽<br>
• <b>经验要求：</b>几乎全部要求5-10年经验<br><br>
⚠️ 这些岗位不适合作为普通产品经理薪资预期。普通求职者应参考中位数（37.5K）、P75（45K）和各方向高薪占比。
</div>
'''

# 第8章公司榜单替换内容
COMPANY_CHAPTER_REPLACEMENT = '''
<div class="card" id="ch8">
  <h2>🏢 第8章：公司与行业机会分析</h2>
  <div class="prose">
    <p>本章基于样本中的公司数据做聚合分析，帮助求职者了解不同类型公司的薪资特征和岗位分布。为保护数据合规，不展示具体公司名称和单家公司明细。</p>
  </div>

  <h3>📊 按公司类型聚合分析</h3>
  <div class="insight">
    <b>大厂（头部互联网平台）：</b>岗位数量最多，薪资中位数略高于整体，高薪岗位集中在AI/大模型、策略产品、商业化方向。投递竞争激烈，需要简历关键词精准匹配。<br><br>
    <b>上市公司：</b>薪资表现稳定，部分新能源/智能硬件上市公司高薪占比突出。适合追求稳定性和品牌背书的求职者。<br><br>
    <b>独角兽/D轮+：</b>薪资上限较高，部分公司高薪占比超过60%，但岗位数量相对有限。适合有明确方向且愿意承担一定风险的求职者。<br><br>
    <b>创业公司：</b>薪资波动较大，少数AI创业公司薪资极高（中位数50K+），但样本少、稳定性存疑。需要仔细评估公司阶段和业务前景。<br><br>
    <b>中型公司：</b>岗位数量中等，薪资表现分化明显——部分金融科技、AI方向中型公司薪资不错，但整体中位数略低于大厂。
  </div>

  <h3>📊 按行业聚合分析</h3>
  <div class="insight">
    <b>互联网（综合）：</b>样本最多，薪资中位数37.5K，是市场基准线。<br>
    <b>人工智能：</b>薪资表现较好，中位数37.5K，P75达45K，高薪岗位集中在大模型/Agent方向。<br>
    <b>智能硬件/消费电子：</b>中位数40K，略高于整体，但岗位方向较垂直。<br>
    <b>电子商务：</b>中位数37.5K，高薪岗位集中在策略/搜推/商业化方向。<br>
    <b>汽车研发/制造：</b>中位数40K，新能源车企薪资表现突出。<br>
    <b>计算机软件：</b>中位数偏低（30K），多为B端/SaaS方向。<br>
    <b>金融/互联网金融：</b>中位数35-37.5K，有行业壁垒，跨行难度大。
  </div>

  <h3>📊 求职启示</h3>
  <div class="insight">
    • 公司类型对薪资有影响，但不应替代方向和JD质量判断<br>
    • 大厂岗位多但竞争激烈，建议同时关注高薪独角兽和优质上市公司<br>
    • 行业选择是辅助维度，核心仍是岗位方向和JD匹配度<br>
    • 建议求职者按"方向→JD质量→公司类型"的优先级筛选，而非只看公司名
  </div>
</div>
'''


def desensitize(html):
    """对 HTML 内容做脱敏处理"""
    
    # 1. 数据来源脱敏
    html = html.replace("Boss直聘", "公开招聘信息样本")
    html = html.replace("BOSS直聘", "公开招聘信息样本")
    html = html.replace("boss直聘", "公开招聘信息样本")
    html = html.replace("Boss 直聘", "公开招聘信息样本")
    
    # 2. 删除 TOP15 高薪岗位明细表，替换为画像
    top15_pattern = r'<h3>🔥 高薪岗位 TOP15</h3>.*?</table>\s*</div>'
    html = re.sub(top15_pattern, f'<h3>🔥 极端高薪岗位画像</h3>\n{TOP15_REPLACEMENT}', html, flags=re.DOTALL)
    
    # 2b. 清理所有"TOP15"残留引用
    html = html.replace("TOP15中大部分岗位由猎头发布", "极端高薪样本中猎头岗位占比较高")
    html = html.replace("TOP15", "极端高薪样本")
    html = html.replace("top15", "极端高薪样本")
    
    # 3. 第8章公司榜单整体替换
    ch8_pattern = r'<div class="card" id="ch8">.*?</div>\s*(?=<div class="card" id="ch9">|<div class="card" id="ch10">|<!-- ═══ 第9章)'
    html = re.sub(ch8_pattern, COMPANY_CHAPTER_REPLACEMENT + '\n', html, flags=re.DOTALL)
    
    # 3b. 如果上面的正则没匹配到（结构不同），尝试另一种方式
    if "招聘活跃公司" in html:
        # 删除招聘活跃公司表格区域
        html = re.sub(r'<h3>📊 招聘活跃公司.*?(?=<h3>📊 高薪公司|<h3>📊 求职启示|</div>\s*</div>)', '', html, flags=re.DOTALL)
        # 删除高薪公司表格区域
        html = re.sub(r'<h3>📊 高薪公司.*?(?=<h3>📊 求职启示|</div>\s*</div>)', '', html, flags=re.DOTALL)
    
    # 4. 公司名脱敏（按长度降序替换）
    for company in sorted(COMPANY_MAP.keys(), key=len, reverse=True):
        html = html.replace(company, COMPANY_MAP[company])
    
    # 5. 商圈标注中的公司名
    html = re.sub(r'（主要为[^）]+）', '', html)
    
    # 6. 删除"建议参考真实公司名"类表述
    html = re.sub(r'[^<]*参考上方招聘活跃公司[^<]*真实公司名[^<]*', '', html)
    html = re.sub(r'[^<]*参考.*?真实公司名[^<]*', '', html)
    
    # 7. 单岗位精确薪资模糊化（处理 "数字-数字K·数字薪" 格式）
    def fuzzy_salary(m):
        text = m.group(0)
        nums = re.findall(r'(\d+)', text)
        if nums:
            low = int(nums[0])
            if low >= 200:
                return "200K+"
            elif low >= 150:
                return "150K+"
            elif low >= 100:
                return "100K+"
            elif low >= 80:
                return "80-100K"
            elif low >= 60:
                return "60-80K"
            elif low >= 50:
                return "50-60K"
        return text
    
    # 处理带"薪"的格式
    html = re.sub(r'\d{2,3}-\d{2,3}K[·.]\d+薪', fuzzy_salary, html)
    # 处理不带"薪"的高薪格式（>50K）
    html = re.sub(r'(?<=>)\s*(\d{3})-(\d{3})K\s*(?=<)', lambda m: f' {fuzzy_salary(m)} ', html)
    
    # 8. 删除"来源"列（猎头/直招）
    html = re.sub(r'<th>来源</th>', '', html)
    html = re.sub(r'<td>猎头</td>', '', html)
    html = re.sub(r'<td>直招</td>', '', html)
    
    # 9. 个人化表达清理（在结论/建议性文字中）
    # 保留数据表格中自然出现的标签词，只清理建议性文字中的个人化内容
    personal_advice_patterns = [
        r'把智能家居经验包装成[^<。]*[<。]',
        r'把多端协同经验包装成[^<。]*[<。]',
        r'智能家居/IoT/多端协同背景[^<。]*[<。]',
        r'米家[^<。]*经验[^<。]*[<。]',
    ]
    for pat in personal_advice_patterns:
        html = re.sub(pat, '', html)
    
    # 10. 添加免责声明（在 header 后面）
    if DISCLAIMER not in html:
        html = html.replace('</div>\n\n<!-- ═══', f'</div>\n{DISCLAIMER}\n<!-- ═══', 1)
    
    # 11. 页脚脱敏
    html = html.replace("公开招聘信息样本数据分析系统自动生成", "招聘市场数据分析系统自动生成")
    html = re.sub(r'报告由.*?自动生成', '报告由招聘市场数据分析系统自动生成', html)
    
    return html


def main():
    print("=" * 50)
    print("  公开分享版报告生成")
    print("=" * 50)
    
    # 读取原始 HTML
    print("\n📥 读取 v18 HTML...")
    with open(INPUT_HTML, "r", encoding="utf-8") as f:
        html = f.read()
    
    # 脱敏处理
    print("🔒 脱敏处理中...")
    html_public = desensitize(html)
    
    # 保存公开版 HTML
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_public)
    print(f"   HTML 已保存: {OUTPUT_HTML}")
    
    # 验证脱敏效果
    print("\n🔍 脱敏验证...")
    plain = re.sub(r'<[^>]+>', '', html_public)
    issues = []
    if "Boss直聘" in plain or "BOSS直聘" in plain:
        issues.append("仍有Boss直聘字样")
    # 检查真实公司名
    for company in ["字节跳动", "京东集团", "百度", "腾讯", "阿里巴巴集团", "小米", "快手", "美团", "滴滴", "小红书", "理想汽车"]:
        if company in plain:
            issues.append(f"仍有公司名: {company}")
    # 检查TOP15残留
    if "TOP15" in plain:
        issues.append("仍有TOP15字样")
    # 检查招聘活跃公司榜单
    if "招聘活跃公司" in plain:
        issues.append("仍有招聘活跃公司榜单")
    # 检查高薪公司排名
    if "高薪公司 TOP" in plain:
        issues.append("仍有高薪公司排名")
    # 检查单岗位精确薪资
    precise_salary = re.findall(r'\d{3}-\d{3}K[·.]\d+薪', plain)
    if precise_salary:
        issues.append(f"仍有精确薪资: {precise_salary[:3]}")
    # 检查猎头/直招绑定
    if re.search(r'(猎头|直招).{0,20}(岗位|公司|薪资)', plain):
        pass  # 聚合描述中可以出现
    
    if issues:
        print(f"   ⚠️ 发现问题: {issues}")
    else:
        print("   ✅ 脱敏验证通过")
    if issues:
        print(f"   ⚠️ 发现问题: {issues}")
    else:
        print("   ✅ 脱敏验证通过")
    
    # 生成长图
    print("\n📸 生成长图 PNG...")
    asyncio.run(_generate_png(OUTPUT_HTML, OUTPUT_PNG))
    
    size_html = os.path.getsize(OUTPUT_HTML) / 1024
    size_png = os.path.getsize(OUTPUT_PNG) / 1024 / 1024
    print(f"\n✅ 完成！")
    print(f"   公开版 HTML: {OUTPUT_HTML} ({size_html:.0f}KB)")
    print(f"   公开版长图: {OUTPUT_PNG} ({size_png:.1f}MB)")


async def _generate_png(html_path, png_path):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1200, "height": 800})
        await page.goto(f"file://{os.path.abspath(html_path)}")
        await page.wait_for_timeout(4000)
        await page.screenshot(path=png_path, full_page=True)
        await browser.close()


if __name__ == "__main__":
    main()
