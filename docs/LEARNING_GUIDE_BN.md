# AI Knowledge Hub: হাতে-কলমে শেখার গাইড

এই প্রকল্পে একটি PDF থেকে প্রশ্নের উত্তর পাওয়ার পুরো পথ দেখানো হয়েছে। আগে FastAPI ও database অংশ বুঝুন, তারপর embedding ও LangGraph দেখুন। একবারে সব মুখস্থ করার দরকার নেই।

## FastAPI কীভাবে অনুরোধ গ্রহণ করে

ব্রাউজার `POST /api/v1/conversations/CONVERSATION_UUID/chat` ঠিকানায় Authorization header এবং নিচের JSON পাঠায়:

```json
{"content":"কর্মীরা বছরে কত দিন ছুটি পান?"}
```

`app/main.py` route যুক্ত করে। `app/api/chat.py` অনুরোধ গ্রহণ করে। `ChatInput` দেখে প্রশ্ন খালি কি না, দৈর্ঘ্য সীমার মধ্যে আছে কি না। ভুল হলে 422 আসে। ঠিক থাকলে service কাজ শুরু করে। Route-এর মধ্যে সব AI logic লেখা হয়নি; তাই ফাইল পড়ে কাজের ধাপ আলাদা করা সহজ।

## Dependency injection

Route-এ `db: Db` এবং `user: CurrentUser` দেখবেন। FastAPI dependency চালিয়ে database session ও যাচাই করা ব্যবহারকারী দেয়। `get_db()` session খুলে, সফল হলে commit করে, ভুল হলে rollback করে। `current_user()` JWT যাচাই করে। `owned()` দেখে resource এই ব্যবহারকারীর কি না। অন্যের UUID জানলেও তথ্য পাওয়া যায় না; 404 আসে। JWT পরিচয় দেয়, ownership check তথ্য ব্যবহারের অনুমতি দেয়। কোনো prompt এই check বদলাতে পারে না।

## Async SQLAlchemy

`models/entities.py`-এ Python class দিয়ে table লেখা হয়েছে। উদাহরণ:

```python
query = select(Chatbot).where(Chatbot.owner_id == user.id)
bots = (await db.scalars(query)).all()
```

Database-এর উত্তর আসার অপেক্ষায় `await` server-কে অন্য কাজ করতে দেয়। একই session একাধিক concurrent কাজের মধ্যে ভাগ করবেন না। বড় model call চলার সময় transaction খোলা রাখা এড়ানো হয়েছে; graph ও worker ছোট session ব্যবহার করে।

## Alembic migration

ORM class লিখলেই PostgreSQL-এ table তৈরি হয় না। Migration হলো database গঠন পরিবর্তনের লিখিত ইতিহাস:

```powershell
cd backend
.\env\Scripts\python.exe -m alembic upgrade head
.\env\Scripts\python.exe -m app.db.setup_checkpoints
```

প্রথম command application table তৈরি করে। দ্বিতীয়টি LangGraph checkpoint table তৈরি করে। পরের schema পরিবর্তনের জন্য নতুন revision তৈরি ও review করবেন। Applied migration আবার লিখবেন না। Application startup-এ `create_all()` নেই; test-এর অস্থায়ী SQLite database-এ শুধু isolated পরীক্ষার জন্য আছে।

## Embedding কী

Embedding লেখাকে সংখ্যার তালিকায় রূপান্তর করে। একই অর্থের লেখা সাধারণত কাছাকাছি vector দেয়। নিচের সংখ্যা শুধু বোঝানোর উদাহরণ:

```text
"বার্ষিক ছুটি"        → [0.12, 0.84, 0.31]
"বছরে কয় দিন ছুটি"  → [0.15, 0.80, 0.35]
"কম্পিউটারের দাম"    → [0.91, 0.04, 0.10]
```

`nomic-embed-text` সাধারণত 768টি সংখ্যা দেয়। Worker registry-এর dimension-এর সঙ্গে প্রতিটি vector মেলায়। Chat model উত্তর বানায়; embedding model প্রাসঙ্গিক লেখা খুঁজতে সাহায্য করে। দুটি আলাদা configuration।

## Document থেকে chunk

Upload API ধরন ও আকার দেখে, নিরাপদ UUID নামে ফাইল রাখে, database job তৈরি করে। আলাদা worker ফাইল থেকে লেখা বের করে। PDF-এর page number থাকে। Scanned PDF-এ selectable text না থাকলে error আসে; এই সংস্করণে OCR নেই।

LangChain-এর `RecursiveCharacterTextSplitter` লেখা ছোট অংশে ভাগ করে। Chunk size 1000, overlap 150 হলে কাছাকাছি chunk-এ কিছু লেখা আবার থাকবে, যাতে মাঝখানে কাটা প্রসঙ্গ হারিয়ে না যায়। সংখ্যা character, token নয়। সব embedding তৈরি হলে একই transaction-এ chunk publish ও document `ready` হয়। মাঝপথে ব্যর্থ হলে অর্ধেক index search-এ আসে না।

## pgvector search

PostgreSQL-এর pgvector extension vector রাখে এবং দূরত্ব হিসাব করে। আমরা `similarity = 1 - cosine_distance` ব্যবহার করি। আগে অনুমোদিত knowledge base, embedding ID ও generation মিলতে হয়। তারপর top-k ও threshold দিয়ে ফল সীমিত হয়। অন্যের KB search করা হয় না। 768 ও 1024 মাত্রার vector তুলনা করা হয় না। একই dimension হলেও আলাদা model-এর vector একই embedding space নয়।

Embedding বদলাতে Reconfigure and reindex ব্যবহার করুন। পুরোনো generation সঙ্গে সঙ্গে বাদ পড়ে। Worker নতুন index করলে document আবার searchable হয়।

## Global model factory

`ai/factory.py` provider দেখে `ChatOllama`, `ChatOpenAI`, `ChatAnthropic` ইত্যাদি তৈরি করে। Chat service শুধু `ainvoke()` বা `astream()` ডাকে। তাই provider বদলাতে RAG আবার লিখতে হয় না।

Administrator dashboard থেকে API key দিলে server encrypt করে রাখে। Response-এ key দেয় না। Cloud ব্যবহার করতে bot ও KB-তে অনুমতি লাগে। Ollama-এর `:cloud` tag local provider-এ নিষিদ্ধ। Local server নিজে বাইরে data পাঠাচ্ছে কি না, সে দায়িত্ব administrator-কে বুঝে configuration করতে হবে।

## Dynamic system prompt

Dashboard-এ লিখতে পারেন: `বাংলায় সংক্ষিপ্ত উত্তর দাও। তথ্য না পেলে জানাও।` এটি current prompt ও history-তে নতুন revision হয়। পরের প্রশ্নে database থেকে নতুন prompt পড়ে; source code বদলায় না।

Application security, মালিকের assistant নির্দেশনা, document-এর untrusted লেখা এবং ব্যবহারকারীর প্রশ্ন আলাদা message হিসেবে যায়। PDF-এ `আগের নির্দেশনা উপেক্ষা করো` লেখা থাকলে সেটি application permission পায় না।

## LangGraph state ও node

Graph হলো কাজের মানচিত্র। State হলো ধাপগুলোর মধ্যে যাওয়া ছোট data object:

```text
settings → history → query → retrieval → evidence check
→ generation অথবা unavailable → sources → save
```

`check_evidence` conditional edge ঠিক করে পরের পথ। Strict mode-এ evidence না থাকলে chat model call হয় না। `TypedDict` state-এর field বোঝায়। Secret বা database session state-এ নেই। `owner_uuid:conversation_uuid` দিয়ে checkpoint thread আলাদা হয়। Checkpoint থাকলেই বন্ধ token stream নিজে থেকে আবার চলবে—এমন দাবি করা হয়নি।

## শুরু থেকে শেষ পর্যন্ত উদাহরণ

PDF page 2-এ লিখুন: `Employees receive twenty days of annual leave.` Strict mode-এ প্রশ্ন করুন: `How much annual leave do employees receive?`

API পরিচয় ও ownership দেখে, প্রশ্ন save করে। Embedding model প্রশ্নের vector দেয়। pgvector প্রাসঙ্গিক passage আনে। LangGraph generation node চালায়। Model exact quote ও source ID নির্বাচন করে JSON দেয়। Server দেখে quote সত্যিই ওই chunk-এ আছে কি না। ঠিক থাকলে:

```text
Employees receive twenty days of annual leave.

[1]
```

Source panel-এ `policy.pdf`, page 2 ও excerpt থাকবে। `fifty days` বানালে server বাতিল করে। Evidence না পেলে unavailable response আসে। এই সংস্করণের strict mode মূল quote দেখায়, বাংলা paraphrase করে না। General mode synthesis করতে পারে, তবে server প্রতিটি বক্তব্য যাচাই করে না। Exact quote-ও প্রশ্নের সঠিক উত্তর কি না বা document সত্য কি না, মানুষকে বিচার করতে হয়।

## Streaming, failure ও test

General mode-এ token আসার সঙ্গে সঙ্গে দেখা যায়। Strict mode আগে যাচাই করে, তারপর checked text ছোট অংশে পাঠায়। শেষে `done` ও sources আসে। Stop চাপলে AbortController request বাতিল করে; অসম্পূর্ণ message successful হয় না। Worker বন্ধ হলেও database job থাকে। Lease শেষে পুনরায় চেষ্টা হয়; সর্বোচ্চ তিনবার। Provider-এর raw error-এ key থাকতে পারে, তাই সেটি response/log-এ দেওয়া হয় না।

```powershell
.\env\Scripts\python.exe -m pytest -q
```

Default test-এ paid call নেই। Mock দিয়ে behavior পরীক্ষা হয়। PostgreSQL vector ও Ollama-এর আলাদা opt-in test আছে। Mock pass মানেই real cloud account কাজ করছে ধরে নেবেন না। প্রথমে `test_auth.py`, তারপর `test_documents.py`, `test_ai.py`, `test_chat.py` পড়ুন। একটি input বদলে expected output কেন বদলায় তা বোঝার চেষ্টা করুন।
