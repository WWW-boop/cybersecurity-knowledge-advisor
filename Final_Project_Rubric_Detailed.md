# Rubric ระดับคุณภาพสำหรับประเมิน Final Project

> เอกสารสรุปและถอดรายละเอียดจากไฟล์ **Rubric ระดับคุณภาพสำหรับประเมิน Final Project** โดยคงโครงสร้างและเกณฑ์การประเมินตามต้นฉบับให้ครบถ้วน

---

## 1. ภาพรวมการประเมิน Final Project

การประเมิน Final Project ใช้ **ระดับคุณภาพ 5 ระดับ** เพื่อวัดความสามารถของโครงการ ตั้งแต่การพัฒนาระบบพื้นฐาน ไปจนถึงการออกแบบระบบ RAG ที่มีการบูรณาการเทคโนโลยีต่าง ๆ อย่างเป็นระบบ ได้แก่

- Dense Retrieval
- Graph RAG
- Hybrid RAG
- Local LLM
- API LLM

การพิจารณาคะแนน **ไม่ได้ดูเพียงว่ามี Technology หรือไม่** แต่พิจารณาถึง

1. คุณภาพของการนำเทคโนโลยีไปใช้งานจริง
2. ความถูกต้องของการออกแบบ
3. การบูรณาการระบบ
4. ประสิทธิภาพของระบบ
5. ความสามารถในการวิเคราะห์ผลการทดลอง

---

## 2. ระดับคุณภาพโดยรวม

| ระดับ | ระดับคุณภาพ | ลักษณะของ Project |
|---|---|---|
| **Level 5** | Excellent / Advanced | ระบบสมบูรณ์ มีการบูรณาการเทคโนโลยีอย่างเหมาะสม มีการทดลองและวิเคราะห์เชิงลึก |
| **Level 4** | Very Good | ระบบครบตามข้อกำหนด ทำงานได้ดี และมีการปรับปรุงหรือประเมินผลอย่างชัดเจน |
| **Level 3** | Good / Satisfactory | ระบบทำงานได้ตามข้อกำหนดหลัก แต่การบูรณาการและการวิเคราะห์ยังมีข้อจำกัด |
| **Level 2** | Basic / Developing | มีการพัฒนาองค์ประกอบบางส่วน แต่ระบบยังไม่สมบูรณ์หรือทำงานร่วมกันได้จำกัด |
| **Level 1** | Limited / Beginning | มี Prototype หรือการสาธิตบางส่วน แต่ไม่สามารถแสดงระบบ RAG ตามข้อกำหนดได้ครบถ้วน |

---

# 3. เกณฑ์ประเมินรายด้าน

## 3.1 Data & Knowledge Base

### Level 5
มีการออกแบบ Dataset และ Knowledge Base อย่างเป็นระบบ โดยมีองค์ประกอบสำคัญครบ เช่น

- Data Cleaning
- Chunking
- Metadata
- การเตรียมข้อมูลสำหรับ Vector
- การเตรียมข้อมูลสำหรับ Graph
- การอธิบายเหตุผลของการออกแบบได้
- ข้อมูลมีคุณภาพเพียงพอสำหรับการทดลอง

### Level 4
- เตรียมข้อมูลสำหรับ Vector และ Graph ได้ครบ
- มีการจัดโครงสร้างข้อมูลอย่างเหมาะสม
- มีการทำความสะอาดข้อมูล
- แต่ยังขาดการปรับปรุงหรือวิเคราะห์ข้อมูลบางส่วน

### Level 3
- มี Dataset
- สามารถนำข้อมูลไปสร้าง Vector และ Graph ได้
- แต่การเตรียมข้อมูลยังอยู่ในระดับพื้นฐาน

### Level 2
- มี Dataset
- แต่การเตรียมข้อมูลยังไม่สมบูรณ์
- อาจมีปัญหาเรื่อง
  - Chunking
  - Metadata
  - Graph Structure

### Level 1
- มีข้อมูลสำหรับทดลองเพียงเล็กน้อย
- หรือไม่สามารถอธิบายกระบวนการเตรียมข้อมูลได้

### สิ่งที่ควรมีหากต้องการได้ Level 5

- Dataset ที่ชัดเจนและมีคุณภาพ
- ขั้นตอน Data Cleaning ที่อธิบายได้
- วิธี Chunking ที่มีเหตุผล
- Metadata ที่ช่วยในการค้นคืน
- โครงสร้าง Graph ที่สอดคล้องกับ Domain
- แสดงตัวอย่างก่อน/หลังการเตรียมข้อมูล
- อธิบายได้ว่าทำไมเลือก Chunk Size, Overlap หรือ Metadata แบบนั้น

---

## 3.2 Dense RAG

### Level 5
Dense RAG ทำงานครบตั้งแต่

**Embedding → Vector Retrieval → Context Selection → LLM**

และมีการปรับ Retrieval เช่น

- Top-K
- Similarity Threshold
- Reranking
- วิธีอื่น ๆ ที่ช่วยเพิ่มคุณภาพ Retrieval

พร้อมมีผลการทดลองยืนยันคุณภาพ

### Level 4
- Dense RAG ทำงานครบ
- ให้ผลลัพธ์เหมาะสม
- มีการกำหนด Retrieval Strategy อย่างชัดเจน

### Level 3
- Dense RAG ทำงานได้จริงตั้งแต่ Vector Search ถึง LLM
- แต่ใช้ Configuration พื้นฐาน
- ยังไม่มีการปรับปรุงมากนัก

### Level 2
- สามารถสร้าง Vector Search ได้
- แต่การนำ Retrieval มาใช้ร่วมกับ LLM ยังไม่สมบูรณ์

### Level 1
- มีเพียง Embedding / Vector Database / Prototype
- แต่ยังไม่สามารถแสดง Dense RAG ที่ทำงานครบกระบวนการได้

### สิ่งที่ควรมีหากต้องการได้ Level 5

- เลือก Embedding Model อย่างมีเหตุผล
- มี Vector Database หรือ Vector Index
- ทดลองหลายค่า Top-K
- ทดลอง Similarity Threshold
- มี Reranking หรือ Context Filtering
- เปรียบเทียบ Configuration หลายแบบ
- วัดผล Retrieval ด้วย Metrics หรือ Test Set

---

## 3.3 Graph RAG

### Level 5
- ออกแบบ Knowledge Graph ได้เหมาะสม
- Node และ Relationship มีความหมาย
- ใช้ Graph Retrieval เพื่อสนับสนุนการตอบคำถามจริง
- สามารถอธิบายได้ว่า Graph ช่วยแก้ข้อจำกัดของ Dense Retrieval อย่างไร

### Level 4
- Graph RAG ทำงานได้จริง
- มี Graph Query / Retrieval
- นำข้อมูลจาก Graph เข้าสู่ LLM ได้อย่างถูกต้อง

### Level 3
- มี Graph Database
- ใช้ Graph Retrieval ร่วมกับ LLM ได้
- แต่การออกแบบ Graph หรือการใช้ประโยชน์จาก Relationship ยังอยู่ในระดับพื้นฐาน

### Level 2
- สร้าง Graph ได้
- แต่การนำ Graph มาใช้ใน Retrieval หรือการสร้างคำตอบยังจำกัด

### Level 1
- มีเพียง Graph Database
- หรือมี Node / Relationship ตัวอย่าง
- แต่ยังไม่สามารถแสดง Graph RAG ที่ใช้งานจริงได้

### สิ่งที่ควรมีหากต้องการได้ Level 5

- Schema ของ Graph ที่ออกแบบตาม Domain
- Node Type และ Relationship Type ชัดเจน
- มี Graph Query เช่น Cypher หรือวิธีค้นคืนจาก Graph
- แสดงตัวอย่าง Query ที่ Graph ตอบได้ดีกว่า Vector Search
- อธิบายประโยชน์ของ Relationship
- แสดงเส้นทางความสัมพันธ์ที่ใช้สร้างคำตอบ

---

## 3.4 Hybrid RAG

> **หัวข้อนี้ควรเป็นหัวใจสำคัญของการประเมิน**

### Level 5
สามารถบูรณาการ Dense Retrieval และ Graph Retrieval ได้อย่างเป็นระบบ โดยมีองค์ประกอบ เช่น

- Fusion
- Ranking
- Routing
- Context Aggregation

และมีผลการทดลองแสดงให้เห็นถึงประโยชน์ของ Hybrid RAG อย่างชัดเจน

### Level 4
- ใช้ Dense และ Graph Retrieval ร่วมกันได้จริง
- มีกระบวนการรวมผลลัพธ์อย่างชัดเจน
- ระบบทำงานได้ดี

### Level 3
- รวม Dense และ Graph Retrieval ในระบบเดียวกันได้
- แต่ Fusion หรือการเลือก Context ยังเป็นวิธีพื้นฐาน

### Level 2
- มีทั้ง Dense และ Graph
- แต่ส่วนใหญ่ทำงานแยกกัน
- หรือการเชื่อมต่อระหว่าง Retrieval ทั้งสองแบบยังไม่ชัดเจน

### Level 1
- มี Dense และ Graph อยู่ใน Project
- แต่ไม่ได้ใช้ร่วมกันในการสร้างคำตอบ

### สิ่งที่ควรมีหากต้องการได้ Level 5

- Dense Retrieval และ Graph Retrieval ต้องทำงานใน Pipeline เดียวกัน
- มีวิธี Fusion ที่ชัดเจน
- อาจมีคะแนนสำหรับจัดอันดับผลลัพธ์
- มี Routing ว่าคำถามแบบใดควรไป Dense, Graph หรือทั้งคู่
- มี Context Aggregation ก่อนส่งเข้า LLM
- เปรียบเทียบ Dense vs Graph vs Hybrid ด้วยชุดคำถามเดียวกัน
- แสดงว่าทำไม Hybrid ดีกว่าในบางกรณี

---

## 3.5 Local LLM

### Level 5
- เลือก Local LLM ได้เหมาะสมกับ Hardware และงาน
- มีการปรับ
  - Configuration
  - Prompt
  - Context
- มีการวัด
  - Resource Usage
  - Response Time
  - ข้อจำกัดของ Model
- มีการวิเคราะห์อย่างเป็นระบบ

### Level 4
- Local LLM ทำงานร่วมกับ RAG ได้ดี
- มีการวิเคราะห์ Model หรือ Resource อย่างเหมาะสม

### Level 3
- Local LLM ทำงานร่วมกับ RAG ได้จริง
- แต่ใช้ Configuration พื้นฐาน

### Level 2
- สามารถเรียก Local LLM ได้
- แต่การเชื่อมต่อกับ RAG ยังไม่สมบูรณ์

### Level 1
- มีการติดตั้งหรือทดลอง Model
- แต่ไม่สามารถใช้งานในระบบจริงได้

### สิ่งที่ควรมีหากต้องการได้ Level 5

- เหตุผลในการเลือก Model
- ขนาด Model และข้อจำกัด Hardware
- Context Length
- Temperature / Top-p / Max Tokens
- เวลาตอบเฉลี่ย
- RAM / VRAM / CPU / GPU Usage
- วิเคราะห์ข้อดีและข้อจำกัดของ Local LLM

---

## 3.6 API LLM

### Level 5
API LLM ถูกนำมาใช้งานจริง โดยมีการจัดการ

- Prompt
- Context
- Token
- Error

และมีการวิเคราะห์

- Response Time
- Cost หรือ Resource Usage

### Level 4
- API LLM ทำงานร่วมกับ RAG ได้ดี
- มีการวิเคราะห์ผลลัพธ์

### Level 3
- API LLM ทำงานร่วมกับ RAG ได้จริงในระดับพื้นฐาน

### Level 2
- สามารถเรียก API ได้
- แต่ยังไม่สามารถบูรณาการกับระบบ RAG ได้อย่างสมบูรณ์

### Level 1
- มีเพียงการทดลองเรียก API
- หรือยังไม่สามารถใช้งานจริง

### สิ่งที่ควรมีหากต้องการได้ Level 5

- API LLM อยู่ใน Pipeline จริง
- จัดการ Prompt และ Context ชัดเจน
- ตรวจ Token Usage
- มี Error Handling
- วัด Latency
- ถ้ามีค่าใช้จ่าย ให้ประมาณ Cost
- เปรียบเทียบผลกับ Local LLM

---

## 3.7 System Integration

### Level 5
ทุกองค์ประกอบทำงานเป็นระบบเดียวกัน ตั้งแต่

**User → Query Processing → Dense/Graph Retrieval → Hybrid Fusion → LLM → Answer**

พร้อมมี

- Error Handling
- Architecture ที่ชัดเจน

### Level 4
- องค์ประกอบหลักทำงานร่วมกันได้ครบ
- มี Workflow ชัดเจน

### Level 3
- ระบบทำงานครบตามข้อกำหนด
- แต่ Architecture ยังเป็นพื้นฐาน

### Level 2
- องค์ประกอบแต่ละส่วนทำงานได้
- แต่การเชื่อมต่อระหว่างส่วนยังมีปัญหา

### Level 1
- เป็น Prototype หลายส่วน
- แต่ยังไม่สามารถทำงานร่วมกันได้

### สิ่งที่ควรมีหากต้องการได้ Level 5

- Architecture Diagram
- Workflow Diagram
- Input/Output ของแต่ละ Module ชัดเจน
- Error Handling
- Logging
- ระบบ Retrieval และ LLM เชื่อมกันครบ
- ผู้ใช้สามารถใช้งานผ่าน Interface เดียว

---

## 3.8 Evaluation & Experimental Analysis

### Level 5
มีการออกแบบการทดลองอย่างเป็นระบบ โดยเปรียบเทียบ

- Dense RAG
- Graph RAG
- Hybrid RAG
- Local LLM
- API LLM

มี Metrics ที่เหมาะสม และสามารถวิเคราะห์สาเหตุของผลลัพธ์ได้

### Level 4
- มีการทดลองและเปรียบเทียบหลาย Configuration
- มี Metrics
- มีการวิเคราะห์ผล

### Level 3
- มี Test Dataset
- มีผลการทดลองพื้นฐาน
- แต่การวิเคราะห์ยังไม่ลึก

### Level 2
- มีการทดสอบระบบ
- แต่ไม่มีการเปรียบเทียบ
- หรือไม่มี Metrics ที่ชัดเจน

### Level 1
- แสดงเพียงตัวอย่างคำตอบหรือ Demo
- ไม่มีการประเมินผลอย่างเป็นระบบ

### สิ่งที่ควรมีหากต้องการได้ Level 5

- สร้าง Test Dataset
- มี Gold Answer หรือเกณฑ์ประเมิน
- เปรียบเทียบหลาย Retrieval Method
- เปรียบเทียบ Local LLM กับ API LLM
- มี Metrics เช่น
  - Precision
  - Recall
  - F1-score
  - Hit Rate / Recall@K
  - MRR
  - Response Time
  - Resource Usage
- วิเคราะห์สาเหตุ ไม่ใช่แค่รายงานตัวเลข

---

# 4. ระดับคุณภาพของ Project โดยรวม

| ระดับ | เกณฑ์พิจารณาโดยรวม |
|---|---|
| **Level 5** | ทุกองค์ประกอบทำงานจริง มี Hybrid RAG ที่สมบูรณ์ มี Evaluation และสามารถวิเคราะห์ผลเชิงลึก |
| **Level 4** | องค์ประกอบหลักครบและทำงานร่วมกันได้ดี มีการทดลองและวิเคราะห์ผล |
| **Level 3** | ระบบครบตามข้อกำหนดและทำงานได้ แต่เป็นการ Implementation ในระดับพื้นฐาน |
| **Level 2** | ทำได้บางองค์ประกอบ แต่ยังขาดการบูรณาการ หรือมีส่วนสำคัญที่ทำงานไม่สมบูรณ์ |
| **Level 1** | เป็น Prototype หรือ Demo บางส่วน และไม่สามารถแสดงการทำงานของระบบตามข้อกำหนดได้ครบ |

---

# 5. หลักการสำคัญในการให้คะแนน

## การมี Technology ไม่เท่ากับการได้ระดับคุณภาพสูง

ตัวอย่างจาก Rubric

- มี Neo4j → **ไม่ได้หมายความว่า Graph RAG อยู่ในระดับสูง**
- มี Vector Database → **ไม่ได้หมายความว่า Dense RAG มีคุณภาพสูง**
- เรียก OpenAI API ได้ → **ไม่ได้หมายความว่า API LLM Integration อยู่ในระดับสูง**
- มีทั้ง Vector + Graph → **ไม่ได้หมายความว่าเป็น Hybrid RAG ระดับสูง**

สิ่งที่ผู้ประเมินต้องการดูคือ

> สามารถนำเทคโนโลยีมาแก้ปัญหาได้จริง และสามารถแสดงหลักฐานจากการทดลองว่าระบบทำงานอย่างมีประสิทธิภาพเพียงใด

ดังนั้น จุดสำคัญไม่ใช่แค่ “มีอะไรบ้าง” แต่ต้องแสดงให้เห็นว่า

1. ทำงานจริง
2. เชื่อมต่อกันจริง
3. เลือกใช้ได้เหมาะสม
4. วัดผลได้
5. วิเคราะห์ผลได้

---

# 6. ตัวอย่างการแยกระดับ Project

## Project A — Level 1

มี

- Vector Database
- Neo4j
- Ollama

แต่แต่ละส่วนทำงานแยกกัน ไม่มี Hybrid RAG และไม่มีผลการทดลอง

---

## Project B — Level 2

- มี Dense RAG
- มี Graph RAG
- ทั้งสองส่วนทำงานได้
- แต่ใช้งานแยกกัน
- ยังไม่มีการเปรียบเทียบผลอย่างเป็นระบบ

---

## Project C — Level 3

มีครบ

- Dense RAG
- Graph RAG
- Hybrid RAG
- Local LLM
- API LLM

แต่

- วิธี Fusion ยังพื้นฐาน
- Evaluation มีเพียงเบื้องต้น

---

## Project D — Level 4

- องค์ประกอบครบ
- ทำงานร่วมกันจริง
- มีการปรับ Retrieval / Fusion
- มีการทดลองเปรียบเทียบ
  - Dense
  - Graph
  - Hybrid
  - Local LLM
  - API LLM

---

## Project E — Level 5

ระบบครบทุกองค์ประกอบ โดยมี

- Architecture ที่เหมาะสม
- Hybrid Retrieval ที่ออกแบบอย่างเป็นระบบ
- การทดลองหลาย Configuration
- Metrics ที่เหมาะสม
- วิเคราะห์ได้ว่าเหตุใดวิธีหนึ่งจึงให้ผลแตกต่างจากอีกวิธีหนึ่ง

---

# 7. ข้อเสนอแนะสำหรับการกำหนดคะแนน 100 คะแนน

| ด้านประเมิน | คะแนนเต็ม |
|---|---:|
| Data & Knowledge Base | 10 |
| Dense RAG | 15 |
| Graph RAG | 15 |
| **Hybrid RAG** | **20** |
| Local LLM + API LLM | 15 |
| System Integration | 10 |
| Evaluation & Analysis | 10 |
| Documentation / Presentation | 5 |
| **รวม** | **100** |

---

# 8. ตัวอย่างการแปลง Level เป็นคะแนน

แต่ละด้านให้ Level 1–5 แล้วแปลงเป็นคะแนนของด้านนั้น

ตัวอย่างกรณี **Hybrid RAG = 20 คะแนน**

| Level | ช่วงคะแนน |
|---|---:|
| Level 5 | 17–20 |
| Level 4 | 13–16 |
| Level 3 | 9–12 |
| Level 2 | 5–8 |
| Level 1 | 0–4 |

---

# 9. Checklist สำหรับทำ Project ให้เข้าใกล้ Level 5

## Data & Knowledge Base
- [ ] มี Dataset ชัดเจน
- [ ] มี Data Cleaning
- [ ] มี Chunking ที่อธิบายเหตุผลได้
- [ ] มี Metadata
- [ ] เตรียมข้อมูลสำหรับ Vector
- [ ] เตรียมข้อมูลสำหรับ Graph
- [ ] อธิบายการออกแบบ Knowledge Base ได้

## Dense RAG
- [ ] มี Embedding
- [ ] มี Vector Retrieval
- [ ] มี Context Selection
- [ ] ส่ง Context เข้า LLM
- [ ] ทดลอง Top-K
- [ ] ทดลอง Similarity Threshold
- [ ] มี Reranking หรือ Filtering
- [ ] มีผลทดลองรองรับ

## Graph RAG
- [ ] มี Knowledge Graph
- [ ] Node มีความหมาย
- [ ] Relationship มีความหมาย
- [ ] มี Graph Query / Retrieval
- [ ] นำ Graph Context เข้า LLM
- [ ] อธิบายประโยชน์ของ Graph เทียบกับ Dense ได้

## Hybrid RAG
- [ ] Dense + Graph ทำงานใน Pipeline เดียวกัน
- [ ] มี Fusion
- [ ] มี Ranking หรือ Context Aggregation
- [ ] มี Routing ถ้าเหมาะสม
- [ ] เปรียบเทียบ Dense vs Graph vs Hybrid
- [ ] มีหลักฐานว่า Hybrid ให้ประโยชน์

## Local LLM
- [ ] เลือก Model เหมาะกับ Hardware
- [ ] เชื่อม Local LLM กับ RAG
- [ ] ปรับ Prompt / Context / Config
- [ ] วัด Response Time
- [ ] วัด Resource Usage
- [ ] วิเคราะห์ข้อจำกัด

## API LLM
- [ ] เชื่อม API LLM กับ RAG
- [ ] จัดการ Prompt
- [ ] จัดการ Context
- [ ] จัดการ Token
- [ ] มี Error Handling
- [ ] วัด Response Time
- [ ] วิเคราะห์ Cost หรือ Resource Usage

## System Integration
- [ ] มี Architecture Diagram
- [ ] มี Workflow Diagram
- [ ] ทุก Module เชื่อมต่อกัน
- [ ] มี Error Handling
- [ ] มี Interface สำหรับผู้ใช้
- [ ] แสดง End-to-End Flow ได้

## Evaluation
- [ ] มี Test Dataset
- [ ] มี Metrics
- [ ] เปรียบเทียบหลาย Configuration
- [ ] เปรียบเทียบ Dense / Graph / Hybrid
- [ ] เปรียบเทียบ Local / API LLM
- [ ] วิเคราะห์สาเหตุของผลลัพธ์

## Documentation / Presentation
- [ ] อธิบาย Architecture ชัดเจน
- [ ] แสดงวิธีทำงานของระบบ
- [ ] แสดงผลการทดลอง
- [ ] แสดงตารางเปรียบเทียบ
- [ ] สรุปข้อดี ข้อจำกัด และสิ่งที่ปรับปรุงได้

---

# 10. สรุปแก่นของ Rubric

หากต้องการให้ Project อยู่ในระดับสูง ไม่ควรหยุดอยู่แค่การ “มีเทคโนโลยีหลายตัว” แต่ต้องทำให้เห็นว่าเทคโนโลยีเหล่านั้น

1. **ถูกออกแบบอย่างเหมาะสม**
2. **เชื่อมต่อกันเป็นระบบจริง**
3. **ทำงานได้แบบ End-to-End**
4. **มีการทดลองเปรียบเทียบอย่างเป็นระบบ**
5. **มี Metrics รองรับ**
6. **สามารถอธิบายสาเหตุของผลลัพธ์ได้**

โดยเฉพาะ **Hybrid RAG** เป็นส่วนสำคัญที่สุดของ Rubric และมีน้ำหนักคะแนนสูงที่สุดที่ **20 คะแนน**

