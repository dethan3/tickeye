# 富文本 post

在一条富文本消息中，支持添加文字、图片、视频、@、超链接等元素。如下 `JSON` 格式的内容是一个富文本示例，其中：

一个富文本可分多个段落（由多个 [] 组成），每个段落可由多个元素组成，每个元素由 tag 和相应的描述组成。
图片、视频元素必须是独立的一个段落。
style 字段暂不支持自定义机器人和批量发送消息接口。
实际发送消息时，需要将 JSON 格式的内容压缩为一行、并进行转义。
如需参考该 JSON 示例构建富文本消息内容，则需要把其中的 user_id、image_key、file_key 等示例值替换为真实值。

## 表格示例

```
{
	"zh_cn": {
		"title": "我是一个标题",
		"content": [
			[
				{
					"tag": "text",
					"text": "第一行:",
					"style": ["bold", "underline"]
                  
				},
				{
					"tag": "a",
					"href": "http://www.feishu.cn",
					"text": "超链接",
					"style": ["bold", "italic"]
				},
				{
					"tag": "at",
					"user_id": "ou_1avnmsbv3k45jnk34j5",
					"style": ["lineThrough"]
				}
			],
          	[{
				"tag": "img",
				"image_key": "img_7ea74629-9191-4176-998c-2e603c9c5e8g"
			}],
			[	
				{
					"tag": "text",
					"text": "第二行:",
					"style": ["bold", "underline"]
				},
				{
					"tag": "text",
					"text": "文本测试"
				}
			],
          	[{
				"tag": "img",
				"image_key": "img_7ea74629-9191-4176-998c-2e603c9c5e8g"
			}],
          	[{
				"tag": "media",
				"file_key": "file_v2_0dcdd7d9-fib0-4432-a519-41d25aca542j",
				"image_key": "img_7ea74629-9191-4176-998c-2e603c9c5e8g"
			}],
          	[{
				"tag": "emotion",
				"emoji_type": "SMILE"
			}],
			[{
				"tag": "hr"
			}],
			[{
				"tag": "code_block",
				"language": "GO",
				"text": "func main() int64 {\n    return 0\n}"
			}],
			[{
				"tag": "md",
				"text": "**mention user:**<at user_id=\"ou_xxxxxx\">Tom</at>\n**href:**[Open Platform](https://open.feishu.cn)\n**code block:**\n```GO\nfunc main() int64 {\n    return 0\n}\n```\n**text styles:** **bold**, *italic*, ***bold and italic***, ~underline~,~~lineThrough~~\n> quote content\n\n1. item1\n    1. item1.1\n    2. item2.2\n2. item2\n --- \n- item1\n    - item1.1\n    - item2.2\n- item2"
			}]
		]
	},
	"en_us": {
		...
	}
}

```
参数说明

名称	类型	是否必填	描述
zh_cn, en_us

object

是

多语言配置字段。如果不需要配置多语言，则仅配置一种语言即可。

zh_cn 为富文本的中文内容
en_us 为富文本的英文内容
注意：该字段无默认值，至少要设置一种语言。

示例值：zh_cn

∟ title

string

否

富文本消息的标题。

默认值：空

示例值：title

∟ content

string

是

富文本消息内容。由多个段落组成（段落由[]分隔），每个段落为一个 node 列表，所支持的 node 标签类型以及对应的参数说明，参见下文的 富文本支持的标签和参数说明 章节。

注意：如 示例值 所示，各类型通过 tag 参数设置。例如文本（text）设置为 "tag": "text"。

示例值：[[{"tag": "text","text": "text content"}]]

富文本支持的标签和参数说明
text：文本标签
名称	类型	是否必填	描述
text

string

是

文本内容。

示例值：test content

un_escape

boolean

否

是否 unescape 解码。默认为 false，无需使用可不传值。

示例值：false

style

[]string

否

文本内容样式，支持的样式有：

bold：加粗
underline：下划线
lineThrough：删除线
italic：斜体
注意：

默认值为空，表示无样式。
传入的值如果不是以上可选值，则被忽略。
示例值：["bold", "underline"]

a：超链接标签
名称	类型	是否必填	描述
text

string

是

超链接的文本内容。

示例值：超链接

href

string

是

超链接地址。

注意：请确保链接地址的合法性，否则消息会发送失败。

示例值：https://open.feishu.cn

style

[]string

否

超链接文本内容样式，支持的样式有：

bold：加粗
underline：下划线
lineThrough：删除线
italic：斜体
注意：

默认值为空，表示无样式。
传入的值如果不是以上可选值，则被忽略。
示例值：["bold", "italic"]

at：@标签
名称	类型	是否必填	描述
user_id

string

是

用户 ID，用来指定被 @ 的用户。传入的值可以是用户的 user_id、open_id、union_id。各类 ID 获取方式参见如何获取 User ID、Open ID 和 Union ID。

注意：

@ 单个用户时，该字段必须传入实际用户的真实 ID。
如需 @ 所有人，则该参数需要传入 all。
style

[]string

否

at 文本内容样式，支持的样式有：

bold：加粗
underline：下划线
lineThrough：删除线
italic：斜体
注意：

默认值为空，表示无样式。
传入的值如果不是以上可选值，则被忽略。
示例值：["lineThrough"]

img：图片标签
名称	类型	是否必填	描述
image_key

string

是

图片 Key。通过上传图片接口可以获取到图片 Key（image_key）。

示例值：d640eeea-4d2f-4cb3-88d8-c964fab53987

media：视频标签
名称	类型	是否必填	描述
file_key

string

是

视频文件的 Key。通过上传文件接口上传视频（mp4 格式）后，可以获取到视频文件 Key（file_key）。

示例值：file_v2_0dcdd7d9-fib0-4432-a519-41d25aca542j

image_key

string

否

视频封面图片的 Key。通过上传图片接口可以获取到图片 Key（image_key）。

默认值：空，表示无视频封面。

示例值：img_7ea74629-9191-4176-998c-2e603c9c5e8g

emotion：表情标签
名称	类型	是否必填	描述
emoji_type

string

是

表情文案类型。可选值参见表情文案说明。

示例值：SMILE

code_block：代码块标签
名称	类型	是否必填	描述
language

string

否

代码块的语言类型。可选值有 PYTHON、C、CPP、GO、JAVA、KOTLIN、SWIFT、PHP、RUBY、RUST、JAVASCRIPT、TYPESCRIPT、BASH、SHELL、SQL、JSON、XML、YAML、HTML、THRIFT 等。

注意：

取值不区分大小写。
不传值则默认为文本类型。
示例值：GO

text

string

是

代码块内容。

示例值：func main() int64 {\n return 0\n}

hr：分割线标签
富文本支持 tag 取值为 hr，表示一条分割线，该标签内无其他参数。

md：Markdown 标签
注意：
md 标签会独占一个或多个段落，不能与其他标签在同一行。
md 标签仅支持发送，获取消息内容时将不再包含此标签，会根据 md 中的内容转换为其他相匹配的标签。
引用、有序、无序列表在获取消息内容时，会简化为文本标签（text）进行输出。
md 标签内通过 text 参数设置 Markdown 内容。

名称	类型	是否必填	描述
text

string

是

Markdown 内容。支持的内容参见下表。

示例值：1. item1\n2. item2

在 text 参数内支持的语法如下表所示。

语法	示例	说明
@ 用户

<at user_id="ou_xxxxx">User</at>

支持 @ 单个用户或所有人。

@ 单个用户时，需要在 user_id 内传入实际用户的真实 ID。传入的值可以是用户的 user_id、open_id、union_id。各类 ID 获取方式参见如何获取 User ID、Open ID 和 Union ID。
如需 @ 所有人，需要将 user_id 取值为 all。
超链接

[Feishu Open Platform](https://open.feishu.cn)

在 Markdown 语法内，[] 用来设置超链接的文本内容、() 用来设置超链接的地址。

注意：请确保链接地址的合法性，否则只发送文本内容部分。

有序列表

1. item1\n2. item2

Markdown 配置说明：

每个编号的 . 符与后续内容之间要有一个空格。
每一列独立一行。如示例所示，可使用 \n 换行符换行。
支持嵌套多层级。
每个层级缩进 4 个空格，且编号均从 1. 开始。
可以与无序列表混合使用。
无序列表

- item1\n- item2

Markdown 配置说明：

每列的 - 符与后续内容之间要有一个空格。
每一列独立一行。如示例所示，可使用 \n 换行符换行。
支持嵌套多层级。
每个层级缩进 4 个空格。
可以与有序列表混合使用，有序列表以 1. 开始编号。
代码块

```GO\nfunc main(){\n return\n}\n```

代码块内容首尾需要使用 ``` 符号包裹，首部 ``` 后紧跟代码语言类型。支持的语言类型有 PYTHON、C、CPP、GO、JAVA、KOTLIN、SWIFT、PHP、RUBY、RUST、JAVASCRIPT、TYPESCRIPT、BASH、SHELL、SQL、JSON、XML、YAML、HTML、THRIFT 等（不区分大小写）。

引用

> demo

引用内容。> 符与后续内容之间要有一个空格。

分割线

\n --- \n

如示例所示，前后需要各有一个 \n 换行符。

加粗

**加粗文本**

配置说明：

** 符与加粗文本之间不能有空格。
加粗可以与斜体合用。例如 ***加粗+斜体***。
加粗的文本不支持再解析其他组件。例如文本为超链接则不会被解析。
斜体

*斜体文本*

配置说明：

* 符与加粗文本之间不能有空格。
斜体可以与加粗合用。例如 ***加粗+斜体***。
斜体的文本不支持再解析其他组件。例如文本为超链接则不会被解析。
下划线

~下划线文本~

配置说明：

~ 符与下划线文本之间不能有空格。
下划线的文本不支持再解析其他组件。例如文本为超链接则不会被解析。
不支持与加粗、斜体、删除线合用。
删除线

~~删除线~~

配置说明：

~~ 符与下划线文本之间不能有空格。
删除线的文本不支持再解析其他组件。例如文本为超链接则不会被解析。
不支持与加粗、斜体、下划线合用。
发送消息时的请求体示例：

{
	"receive_id": "oc_820faa21d7ed275b53d1727a0feaa917",
	"content": "{\"zh_cn\":{\"title\":\"我是一个标题\",\"content\":[[{\"tag\":\"text\",\"text\":\"第一行 :\"},{\"tag\":\"a\",\"href\":\"http://www.feishu.cn\",\"text\":\"超链接\"},{\"tag\":\"at\",\"user_id\":\"ou_1avnmsbv3k45jnk34j5\",\"user_name\":\"tom\"}],[{\"tag\":\"img\",\"image_key\":\"img_7ea74629-9191-4176-998c-2e603c9c5e8g\"}],[{\"tag\":\"text\",\"text\":\"第二行:\"},{\"tag\":\"text\",\"text\":\"文本测试\"}],[{\"tag\":\"img\",\"image_key\":\"img_7ea74629-9191-4176-998c-2e603c9c5e8g\"}]]}}",
	"msg_type": "post"