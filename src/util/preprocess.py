import json
from concurrent.futures import ThreadPoolExecutor

import jieba
import openai
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
openai_client = OpenAI(base_url='https://chatnio.cdreader.vip/v1', max_retries=1024, timeout=1600)
llm = 'qwen-plus'


def split_words(text: str, stopwords: list) -> list:
    known_names = ner(text)
    stopwords.extend(known_names)
    for w in stopwords:
        text = text.replace(w, '_')
    seg_list = jieba.cut(text, cut_all=False)
    return [w for w in seg_list if len(w) > 1 and '_' not in w and not w.isnumeric()]


def llm_based_ner(text: str, field: str = '网文') -> list:
    text = text[:20000]
    role = '命名实体识别算法'
    output_restraint = '你的输出只能在同一行, JSONL格式, 请确保 JSONL 的格式合法.'
    system_prompt = {
        '你是': role,
        '领域': field,
        '输出数据格式': 'JSONL',
        '输出示例': ['沈思', '沉婉', '钟元', '景眠', '叶瑾', '楚修', '苏', '陈'],
        '输出格式限制': output_restraint
    }
    prompt = {
        '文段': text,
        '系统指令设定': system_prompt,
        '任务目标': '请你仔细阅读[文段], 找出文段中所提及的所有**人类命名实体**的**姓名**和**家族名**, 仅找出**姓名**和**家族名**, 不涉及**称谓**. 包括主角, 配角.',
        '提示': '1. 某些人名如"澄映", "舒念", "语歌"等较为拗口甚至和常用词谐音. 请注意: 通常没有实际意义的词汇很可能就是人名, 请你多加注意.\n'
                '2. 对于一些较为拗口的人名, 请你根据上下文确定其性质, 通常人名会和动词介词相关联. 请不要漏过任何一个的人名!',
        '限制': '对于 "陈姨", "铭宝", "吴总" 这样的称谓, 你只需要提取 "陈", "铭", "吴" 即可, 不需要涉及通用称谓. 对于 "陈家", "谢家" 则提取其家族姓氏 "陈", "谢".\n'
                '对于"国王", "皇后", "总裁"等称谓, 它们并不是人名, 不需要提取.',
    }
    while True:
        try:
            response = openai_client.chat.completions.create(
                model=llm,
                messages=[
                    {'role': 'user', 'content': json.dumps(prompt, ensure_ascii=False)},
                    {'role': 'system', 'content': json.dumps(system_prompt, ensure_ascii=False)},
                ],
                temperature=0.1,
                top_p=0.2
            ).choices[0].message.content
            names = json.loads(response[response.find('['): response.find(']') + 1])
            print('GPT NER:', names)
            return names
        except json.decoder.JSONDecodeError:
            ...
        except openai.InternalServerError:
            ...


def ner(text: str) -> list:
    names = []
    chunk_size = 3600
    _split = int(len(text) / chunk_size) + 1
    print('Split:', _split)
    _inputs = []
    for i in range(_split):
        _inputs.append(text[i*chunk_size:(i+1)*chunk_size])
    with ThreadPoolExecutor(max_workers=_split) as executor:
        tmp_names = list(executor.map(llm_based_ner, _inputs))
    for _names in tmp_names:
        names.extend(_names)
    return list(set(names))
