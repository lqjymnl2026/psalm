# -*- coding: utf-8 -*-
"""示例数据 + 示例导入文件。"""
from __future__ import annotations

import io
import os

# (title, firstLine, lyricist, composer, translator, tune, key, source, status, rating)
HYMNS = [
    ("奇异恩典", "奇异恩典，何等甘甜，我罪已得赦免；前我失丧，今被寻回，瞎眼今得看见。", "John Newton", "早期美国曲调", "刘廷芳 等译", "NEW BRITAIN", "G", "示例数据·赞美诗集", "published", 4.9),
    ("奇异恩典 Amazing Grace", "奇异恩典，何等甘甜，我罪已得赦免；前我失丧，今被寻回，瞎眼今得看见。", "John Newton", "NEW BRITAIN", "", "NEW BRITAIN", "G", "示例数据·英文歌本", "pending", 0),
    ("奇异恩典（改编版）", "奇异恩典，何等甘甜，我今已经得赦免；前我失丧，今被寻回，瞎眼今得看见。", "John Newton（改编）", "NEW BRITAIN", "", "NEW BRITAIN", "G", "示例数据·方言版本", "pending", 0),
    ("圣哉圣哉圣哉", "圣哉，圣哉，圣哉！万军之耶和华，你的荣光充满全地。", "Reginald Heber", "John B. Dykes", "", "NICAEA", "E♭", "示例数据·赞美诗集", "final", 4.8),
    ("圣哉三一歌", "圣哉，圣哉，圣哉！万军之耶和华，你的荣光充满全地。", "Reginald Heber", "John B. Dykes", "", "NICAEA", "E♭", "示例数据·重排版", "pending", 0),
    ("万古磐石", "万古磐石为我开，容我藏身在主怀；愿因主流水和血，洗我一生诸罪孽。", "Augustus Toplady", "Thomas Hastings", "刘廷芳 译", "TOPLADY", "F", "示例数据·赞美诗集", "candidate", 4.6),
    ("千古保障", "上主是人千古保障，是人将来希望；是人居所抵御风雨，是人永久家乡。", "Isaac Watts", "William Croft", "刘廷芳 译", "ST ANNE", "C", "示例数据·赞美诗集", "candidate", 4.5),
    ("普世欢腾", "普世欢腾，救主下降，大地迎接君王；惟愿万众，心准备好，与主同进天堂。", "Isaac Watts", "G. F. Handel 改编", "刘廷芳 译", "ANTIOCH", "D", "示例数据·圣诞诗辑", "shortlist", 4.4),
    ("平安夜", "平安夜，圣善夜，万暗中，光华射；照着圣母也照着圣婴，多少慈祥也多少天真，静享天赐安眠。", "Joseph Mohr", "Franz Gruber", "刘廷芳 译", "STILLE NACHT", "C", "示例数据·圣诞诗辑", "final", 4.9),
    ("平安夜歌", "平安夜，圣善夜，万暗中，光华射；照着圣母也照着圣婴，多少慈祥也多少天真，静享天赐安眠。", "Joseph Mohr", "Franz Gruber", "", "STILLE NACHT", "G", "示例数据·简谱版", "pending", 0),
    ("三一颂", "赞美真神万福之源，世上万民都当颂言；天上万军高声颂赞，圣父圣子圣灵同尊。", "Thomas Ken", "早期曲调", "刘廷芳 译", "OLD 100TH", "G", "示例数据·赞美诗集", "shortlist", 4.3),
    ("赞美一神", "赞美真神万福之源，世上万民都当颂言；天上万军高声颂赞，圣父圣子圣灵同尊。", "Thomas Ken", "Louis Bourgeois", "", "OLD 100TH", "G", "示例数据·英文歌本", "pending", 0),
    ("爱主更深", "我愿更加爱主，更亲近主；我愿天天努力，讨主喜悦。", "Sarah F. Adams", "Lowell Mason", "", "BETHANY", "G", "示例数据·赞美诗集", "candidate", 4.2),
    ("我灵镇静", "我灵镇静，上主在你身旁；十架苦难，仍要忍耐担当。", "Katharina von Schlegel", "Jean Sibelius", "刘廷芳 译", "FINLANDIA", "F", "示例数据·安静默想辑", "candidate", 4.7),
    ("荣耀归于真神", "荣耀归于真神，他成就大事，藉爱子耶稣我们得救赎；荣耀归于真神，他成就大事。", "Fanny Crosby", "W. H. Doane", "刘廷芳 译", "TO GOD BE THE GLORY", "A♭", "示例数据·赞美诗集", "final", 4.8),
    ("有福确据", "有福确据，耶稣属我，我今得尝预尝喜乐；信靠救主，满心欢畅，直上天堂。", "Fanny Crosby", "Phoebe Knapp", "", "ASSURANCE", "D", "示例数据·赞美诗集", "candidate", 4.5),
    ("恩友歌", "何等恩友慈仁救主，负我罪孽担我忧；何等权利能将万事，来到耶稣座前求。", "Joseph Scriven", "Charles C. Converse", "刘廷芳 译", "ERIE", "F", "示例数据·赞美诗集", "shortlist", 4.6),
    ("向高处行", "我今直往高处而行，灵性地位日日高升；我求更高境界，更近我主。", "Johnson Oatman Jr.", "Charles H. Gabriel", "", "HIGHER GROUND", "A♭", "示例数据·奋兴诗歌", "candidate", 4.1),
    ("耶稣爱我", "耶稣爱我万不错，因有圣经告诉我；凡小孩子主牧养，我虽软弱主强壮。", "Anna B. Warner", "William B. Bradbury", "", "JESUS LOVES ME", "F", "示例数据·儿童诗歌", "shortlist", 4.8),
    ("荣耀歌", "天使高声唱荣耀，荣耀归于新生王；天上人间齐欢唱，平安归于他所爱。", "法国传统圣诞歌", "法国传统曲调", "", "GLORIA", "G", "示例数据·圣诞诗辑", "candidate", 4.3),
    ("以马内利来临", "以马内利，恳求降临，救赎被掳以色列民；孤独流浪，等候救恩，求主快来，赐予安宁。", "拉丁圣诗（12世纪）", "传统曲调", "", "VENI EMMANUEL", "e", "示例数据·将临期圣诗", "candidate", 4.5),
    ("啊，圣善夜", "啊！圣善夜，众星照耀极光明；今夜良辰，救主降生。", "Placide Cappeau", "Adolphe Adam", "", "CANTIQUE DE NOEL", "G", "示例数据·圣诞诗辑", "shortlist", 4.7),
    ("主是我牧者", "耶和华是我的牧者，我必不至缺乏；他使我躺卧在青草地上，领我到可安歇的水边。", "诗篇23篇", "传统曲调", "", "", "G", "示例数据·经文诗歌", "final", 4.9),
    ("你真伟大", "主啊我神，我每逢举目观看，你手所造一切奇妙大工；看见星宿，又听见隆隆雷声，你的大能遍满了宇宙中。", "Carl Boberg", "瑞典传统曲调", "刘廷芳 译", "O STORE GUD", "A♭", "示例数据·请核对版权", "candidate", 4.8),
    ("十字架歌", "求主使我近十架，在彼有生命水；由各各他山流下，洗净万民罪秽。", "Fanny Crosby", "William H. Doane", "", "NEAR THE CROSS", "F", "示例数据·受难诗辑", "shortlist", 4.6),
    ("宝血活泉", "有一活泉充满宝血，从主身上流出；罪人只要一投其中，立见罪迹全无。", "William Cowper", "Lowell Mason", "刘廷芳 译", "CLEANSING FOUNTAIN", "C", "示例数据·受难诗辑", "candidate", 4.4),
    ("主引导我", "愿主耶稣亲自引导，走那崎岖山道；无论晴雨顺逆环境，主必引导我前行。", "Joseph H. Gilmore", "William B. Bradbury", "", "HE LEADETH ME", "D", "示例数据·赞美诗集", "shortlist", 4.3),
    ("新生王歌", "听啊，天使高声唱，荣耀归于新生王；天上人间诸众生，齐来颂扬救主名。", "Charles Wesley", "Felix Mendelssohn 改编", "刘廷芳 译", "MENDELSSOHN", "F", "示例数据·圣诞诗辑", "candidate", 4.5),
    ("美哉小城", "美哉小城，小伯利恒，安然寂静纯朴；在你深处，救主降生，万古希望成就。", "Phillips Brooks", "Lewis H. Redner", "", "ST LOUIS", "C", "示例数据·圣诞诗辑", "candidate", 4.4),
    ("这位奇妙婴孩是谁", "这位奇妙婴孩是谁，安卧马利亚怀中？夜半牧人欢然高唱，天使同声和应。", "William C. Dix", "传统英国曲调", "", "GREENSLEEVES", "e", "示例数据·圣诞诗辑", "shortlist", 4.2),
    ("普天颂赞", "万民啊，赞美主，同唱凯歌高唱；齐来称谢创造主，万有都当颂扬。", "Francis of Assisi", "传统曲调", "", "LASST UNS ERFREUEN", "F", "示例数据·赞美诗集", "candidate", 4.3),
    ("伟大真神", "伟大真神，隐形真神，光耀居不可测；惟你配得称颂赞美，万有都当屈膝。", "Walter C. Smith", "苏格兰传统曲调", "", "ST DENIO", "G", "示例数据·赞美诗集", "candidate", 4.2),
    ("圣灵降临", "圣灵降临，求临我心，赐我亮光与能力；燃烧我灵，洁净我心，使我完全属于你。", "George Croly", "John B. Dykes", "", "ST CUTHBERT", "A♭", "示例数据·圣灵诗辑", "candidate", 4.5),
    ("主必再来", "主必再来，荣耀驾云降临，万民都要看见；主必再来，号筒吹响，迎接圣徒归天家。", "传统圣诗", "传统曲调", "", "", "D", "示例数据·再来诗辑", "shortlist", 4.4),
    ("基督复生", "基督耶稣今天复生，哈利路亚！天使世人齐声响应，哈利路亚！", "Charles Wesley", "传统曲调", "刘廷芳 译", "EASTER HYMN", "G", "示例数据·复活节诗辑", "final", 4.7),
    ("完全的恩爱", "完全的恩爱，超乎万爱之上，求你赐给这同心伉俪；使他们一生相爱相扶持，直到见主面。", "Dorothy F. Gurney", "Joseph Barnby", "", "O PERFECT LOVE", "E♭", "示例数据·婚礼诗辑", "shortlist", 4.3),
    ("安息日晨光", "安息圣日，晨光初照，万物静候主恩；让我今日放下劳苦，单单敬拜真神。", "传统圣诗", "传统曲调", "", "", "C", "示例数据·安息日诗辑", "pending", 0),
    ("我今受洗", "我今受洗归入主名，与主同死同埋葬；一举一动有新生的样式，与主同活同得胜。", "传统圣诗", "传统曲调", "", "", "F", "示例数据·洗礼诗辑", "candidate", 4.2),
    ("天堂是我家", "世上虽有劳苦艰难，天堂是我家；虽有试炼和忧患，天堂是我家。", "传统圣诗", "传统曲调", "", "", "F", "示例数据·天家诗辑", "shortlist", 4.5),
    ("奋兴祷告", "求主奋兴我灵，复兴你的教会；圣灵火焰燃烧，充满每个心灵。", "传统圣诗", "传统曲调", "", "", "E♭", "示例数据·奋兴诗歌", "candidate", 4.1),
    ("小小双手为主做", "小小双手为主做，小小双脚为主走；小小耳朵听主话，小小嘴唇赞美主。", "儿童诗歌（公有领域）", "传统曲调", "", "", "C", "示例数据·儿童诗歌", "candidate", 4.6),
    ("荣耀圣名", "荣耀、荣耀，归主圣名，万口都要承认；万膝都要向主跪拜，尊主为大为圣。", "传统圣诗", "传统曲调", "", "", "G", "示例数据·赞美诗集", "candidate", 4.2),
    ("主在圣殿中", "主在圣殿中，普世的人当肃静；在主面前，应当肃静，静默礼拜。", "传统圣诗", "传统曲调", "", "", "D", "示例数据·崇拜开始曲", "shortlist", 4.3),
    ("阿们颂", "阿们，阿们，阿们。", "传统圣诗", "传统曲调", "", "", "C", "示例数据·崇拜结束曲", "rejected", 0),
    ("齐来崇拜", "齐来，齐来，众信徒，欢欣快乐来崇拜；齐来，齐来，到伯利恒，来见新生王。", "拉丁圣诗", "John F. Wade", "刘廷芳 译", "ADESTE FIDELES", "G", "示例数据·圣诞诗辑", "final", 4.6),
    ("我的救主", "我的救主，我的君王，我今称颂你圣名；你为我罪舍身十架，宝血洗净我心灵。", "传统圣诗", "传统曲调", "", "", "G", "示例数据·赞美诗集", "pending", 0),
]

LYRICS_EXTRA = {
    "奇异恩典": "\n奇异恩典，何等甘甜，我罪已得赦免；前我失丧，今被寻回，瞎眼今得看见。\n如此恩典，使我敬畏，使我心得安慰；初信之时即蒙恩惠，真是何等宝贵。\n许多危险，试炼网罗，我已安然经过；靠主恩典，安全不怕，更引导我归家。",
    "奇异恩典 Amazing Grace": "\n奇异恩典，何等甘甜，我罪已得赦免；前我失丧，今被寻回，瞎眼今得看见。\n如此恩典，使我敬畏，使我心得安慰；初信之时即蒙恩惠，真是何等宝贵。",
    "圣哉圣哉圣哉": "\n圣哉，圣哉，圣哉！万军之耶和华，你的荣光充满全地。\n圣哉，圣哉，圣哉！昔在今在以后永在，全能真神。",
    "平安夜": "\n平安夜，圣善夜，万暗中，光华射；照着圣母也照着圣婴，多少慈祥也多少天真，静享天赐安眠，静享天赐安眠。\n平安夜，圣善夜，牧羊人，在旷野；忽然看见了天上光华，听见天军唱哈利路亚，救主今夜降生，救主今夜降生。",
    "恩友歌": "\n何等恩友慈仁救主，负我罪孽担我忧；何等权利能将万事，来到耶稣座前求。\n多少平安屡屡失去，多少痛苦白白受；皆因我们未将万事，来到耶稣座前求。",
    "你真伟大": "\n主啊我神，我每逢举目观看，你手所造一切奇妙大工；看见星宿，又听见隆隆雷声，你的大能遍满了宇宙中。\n我灵歌唱，赞美救主我神，你真伟大，何等伟大。",
    "万古磐石": "\n万古磐石为我开，容我藏身在主怀；愿因主流水和血，洗我一生诸罪孽；使我罪孽得洗净，使我干罪得赦免。",
}


def build_seed_songs():
    songs = []
    for i, (title, first, lyricist, composer, translator, tune, key, source, status, rating) in enumerate(HYMNS, start=1):
        lyrics = first + LYRICS_EXTRA.get(title, "")
        s = {
            "id": f"SD{i:04d}",
            "number": f"{i:03d}",
            "title": title,
            "firstLine": first,
            "lyrics": lyrics.strip(),
            "lyricist": lyricist,
            "composer": composer,
            "translator": translator,
            "tune": tune,
            "key": key,
            "meter": "",
            "source": source,
            "comment": "示例数据，正式出版前请核实版权与译词归属",
            "status": status,
            "rating": rating,
            "importBatch": "seed-demo",
            "importSource": "内置示例数据",
            "createdAt": "2026-08-10T08:00:00",
            "updatedAt": "2026-08-10T08:00:00",
            "attachments": [],
            "flags": [],
        }
        songs.append(s)
    return songs


def make_sample_files(samples_dir: str):
    os.makedirs(samples_dir, exist_ok=True)
    # ---- 示例 Excel（列名与标准不同，演示自动匹配）----
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "导入示例"
    ws.append(["歌曲名称", "作者", "作曲者", "调子", "来源", "备注"])
    rows = [
        ("万古磐石", "Augustus Toplady", "Thomas Hastings", "F", "老赞美诗集", ""),
        ("千古保障", "Isaac Watts", "William Croft", "C", "老赞美诗集", ""),
        ("恩友歌", "Joseph Scriven", "Charles C. Converse", "F", "老赞美诗集", ""),
        ("平安夜", "Joseph Mohr", "Franz Gruber", "C", "圣诞诗辑", ""),
        ("奇异恩典", "John Newton", "", "G", "老赞美诗集", ""),
        ("荣耀归于真神", "Fanny Crosby", "W. H. Doane", "A♭", "老赞美诗集", ""),
        ("", "", "", "", "残缺记录", "缺少歌名，应进入待确认"),
        ("有福确据", "Fanny Crosby", "Phoebe Knapp", "D", "老赞美诗集", ""),
    ]
    for r in rows:
        ws.append(list(r))
    wb.save(os.path.join(samples_dir, "赞美诗导入示例.xlsx"))

    # ---- 导入模板（标准列名）----
    wb2 = Workbook()
    ws2 = wb2.active
    ws2.title = "导入模板"
    ws2.append(["歌名", "首句", "作者", "作曲", "译者", "曲调", "调性", "格律", "主题", "来源", "歌词", "备注"])
    ws2.append(["奇异恩典", "奇异恩典，何等甘甜", "John Newton", "NEW BRITAIN", "刘廷芳", "NEW BRITAIN", "G", "8.6.8.6", "恩典", "赞美诗集", "奇异恩典，何等甘甜，我罪已得赦免；前我失丧，今被寻回，瞎眼今得看见。", "填写说明：第一行为表头，请勿修改；没有的字段留空即可"])
    wb2.save(os.path.join(samples_dir, "导入模板.xlsx"))

    # ---- 示例 PDF（每页单独生成再合并，保证可提取文字）----
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.pagesizes import A4
    from pypdf import PdfWriter, PdfReader
    font = "SampleCJK"
    try:
        pdfmetrics.getFont(font)
    except Exception:
        pdfmetrics.registerFont(TTFont(font, "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"))
    pages = [
        [("赞美诗集 · 示例（第一卷）", 15), ("", 8),
         ("001 奇异恩典", 13), ("奇异恩典，何等甘甜，我罪已得赦免；", 11),
         ("前我失丧，今被寻回，瞎眼今得看见。", 11),
         ("002 万古磐石", 13), ("万古磐石为我开，容我藏身在主怀；", 11),
         ("愿因主流水和血，洗我一生诸罪孽。", 11)],
        [("003 平安夜", 13), ("平安夜，圣善夜，万暗中，光华射；", 11),
         ("照着圣母也照着圣婴，多少慈祥也多少天真，静享天赐安眠。", 11),
         ("004 圣哉圣哉圣哉", 13), ("圣哉，圣哉，圣哉！万军之耶和华，", 11),
         ("你的荣光充满全地。", 11)],
        [("005 恩友歌", 13), ("何等恩友慈仁救主，负我罪孽担我忧；", 11),
         ("何等权利能将万事，来到耶稣座前求。", 11),
         ("006 荣耀归于真神", 13), ("荣耀归于真神，他成就大事，", 11),
         ("藉爱子耶稣我们得救赎。", 11)],
    ]
    page_pdfs = []
    for lines in pages:
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        y = 790
        for text, size in lines:
            c.setFont(font, size)
            c.drawString(60, y, text)
            y -= 26
        c.showPage()
        c.save()
        page_pdfs.append(buf.getvalue())
    writer = PdfWriter()
    for p in page_pdfs:
        writer.append(PdfReader(io.BytesIO(p)))
    with open(os.path.join(samples_dir, "赞美诗集示例.pdf"), "wb") as f:
        writer.write(f)
    return [
        "samples/赞美诗导入示例.xlsx",
        "samples/导入模板.xlsx",
        "samples/赞美诗集示例.pdf",
    ]
