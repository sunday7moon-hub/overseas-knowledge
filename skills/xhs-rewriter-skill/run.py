# file: run.py
import sys
import json

def rewrite_article(raw_text, style="网感爆棚"):
    # 这里的核心逻辑定义了洗稿的改写框架（爆款拆解）
    # 大模型或者执行容器拿到这个结构后，会依此进行重构
    prompt_framework = f"""
    【小红书爆款重构任务】
    原文字数及核心痛点保留，但使用以下风格进行全新洗稿：{style}
    
    【重构规则】
    1. 标题（3个备选）：必须包含情绪词（如：家人们、谁懂啊、亲测、封神）和数字，限制20字内。
    2. 正文开头（前3行）：必须在前3秒抓住眼球（痛点引入或反常识结论）。
    3. 正文排版：每两句空一行，大量使用 Emoji（✨、🔥、💡）作为段落开头，增加呼吸感。
    4. 结尾：必须设计一个互动话题（如：你们觉得呢？在评论区聊聊）。
    5. 标签：末尾自动附带 5 个相关热门标签。
    
    【原文内容】
    {raw_text}
    """
    
    # 模拟返回一个结构化的清洗结果
    result = {
        "status": "success",
        "style_applied": style,
        "processed_prompt": prompt_framework.strip()
    }
    return result

if __name__ == "__main__":
    # 龙虾平台会通过标准的命令行参数将参数传给脚本
    try:
        # 从标准输入读取龙虾传入的参数
        input_data = json.loads(sys.stdin.read())
        article = input_data.get("article", "")
        style = input_data.get("style", "网感爆棚")
        
        if not article:
            print(json.dumps({"status": "error", "message": "原文字数不能为空"}))
            sys.exit(1)
            
        output = rewrite_article(article, style)
        # 将结果通过标准输出返回给龙虾
        print(json.dumps(output, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))