import asyncio
# TypedDict: Dùng để tạo khung xương cho dữ liệu (Dictionary có cấu trúc)
# Annotated: Dùng để thêm logic bổ sung cho kiểu dữ liệu
from typing import Annotated, TypedDict

# StateGraph: Lớp chính để xây dựng sơ đồ luồng (Workflow)
# START/END: Các điểm mốc đánh dấu điểm bắt đầu và kết thúc của quy trình
from langgraph.graph import StateGraph, START, END

# add_messages: Hàm đặc biệt giúp cộng dồn tin nhắn vào lịch sử (Memory)
from langgraph.graph.message import add_messages

# ChatOpenAI: Lớp để kết nối với các model dùng chuẩn OpenAI (như model 20B của bạn)
from langchain_openai import ChatOpenAI

# @tool: Decorator để biến một hàm Python bình thường thành công cụ mà AI dùng được
from langchain_core.tools import tool

# ToolNode: Nút chuyên dụng để thực thi các công cụ (Cánh tay của AI)
# tools_condition: Logic kiểm tra xem AI có muốn gọi tool hay không (Rẽ nhánh)
from langgraph.prebuilt import ToolNode, tools_condition

# ---------------------------------------------------------
# BƯỚC 1: ĐỊNH NGHĨA TRẠNG THÁI (STATE)
# ---------------------------------------------------------
# Đây là "trí nhớ chung" của toàn bộ hệ thống.
class State(TypedDict):
    # 'messages' là một danh sách các tin nhắn.
    # add_messages đảm bảo tin nhắn mới được NỐI TIẾP vào danh sách cũ.
    messages: Annotated[list, add_messages]

# ---------------------------------------------------------
# BƯỚC 2: TẠO CÔNG CỤ (TOOLS)
# ---------------------------------------------------------
@tool
def search_stock_price(company: str):
    """Tìm kiếm giá cổ phiếu của một công ty. Hãy dùng tool này khi người dùng hỏi về giá chứng khoán."""
    # Giả lập một database tra cứu giá
    stock_data = {"FPT": "150,000 VND", "VNM": "70,000 VND", "VIC": "45,000 VND"}
    return f"Giá cổ phiếu của {company} hiện tại là {stock_data.get(company, 'không rõ')}."

# Gom các công cụ vào một danh sách để quản lý
tools = [search_stock_price]

# Tạo một Node (nút) chuyên thực thi các công cụ này
# Khi luồng đi vào đây, hàm 'search_stock_price' sẽ thực sự được chạy
tool_node = ToolNode(tools)

# ---------------------------------------------------------
# BƯỚC 3: CẤU HÌNH BỘ NÃO (LLM)
# ---------------------------------------------------------
llm = ChatOpenAI(
    model="openai/gpt-oss-20b",
    openai_api_base="http://50.7.159.181:21276/v1", # URL Swagger của bạn
    openai_api_key="empty",
    temperature=0 # Độ sáng tạo = 0 để AI trả lời chính xác, ít bị "ảo giác"
).bind_tools(tools) # "Dạy" cho AI biết nó có những công cụ này

# ---------------------------------------------------------
# BƯỚC 4: ĐỊNH NGHĨA CÁC NÚT XỬ LÝ (NODES)
# ---------------------------------------------------------

def chatbot(state: State):
    """
    Nút này nhận vào trạng thái (lịch sử chat), 
    gửi cho AI và trả về tin nhắn mới nhất của AI.
    """
    print("\n--- [NODE: chatbot] AI đang suy nghĩ... ---")
    # Lấy toàn bộ tin nhắn trong sổ tay gửi cho AI
    response = llm.invoke(state["messages"])
    # Trả về kết quả dưới dạng dict để LangGraph tự động cập nhật vào State
    return {"messages": [response]}

# ---------------------------------------------------------
# BƯỚC 5: LẮP RÁP SƠ ĐỒ (GRAPH)
# ---------------------------------------------------------
# 1. Khởi tạo bản thiết kế workflow
workflow = StateGraph(State)

# 2. Thêm các "trạm xử lý" vào sơ đồ
workflow.add_node("chatbot", chatbot) # Trạm suy nghĩ
workflow.add_node("tools", tool_node) # Trạm thực thi công cụ

# 3. Nối dây cho sơ đồ
workflow.add_edge(START, "chatbot") # Vừa vào là gặp AI ngay

# 4. Rẽ nhánh có điều kiện sau khi AI suy nghĩ xong
workflow.add_conditional_edges(
    "chatbot",      # Sau khi ở trạm chatbot
    tools_condition # Kiểm tra: Nếu AI trả về 'tool_calls' -> đi tiếp tới 'tools'
                    # Nếu AI trả về văn bản thường -> đi tới END (Kết thúc)
)

# 5. Sau khi thực thi công cụ xong, PHẢI quay lại AI để nó tổng hợp câu trả lời
workflow.add_edge("tools", "chatbot")

# 6. Biên dịch thành ứng dụng hoàn chỉnh
app = workflow.compile()

# ---------------------------------------------------------
# BƯỚC 6: CHẠY THỰC TẾ VÀ XEM LOG
# ---------------------------------------------------------
async def main():
    # Câu hỏi yêu cầu phải dùng công cụ tra cứu
    user_input = {"messages": [("user", "Giá cổ phiếu FPT hiện tại là bao nhiêu?")]}
    
    print("🚀 KHỞI ĐỘNG AGENT...")
    
    # astream giúp ta xem dữ liệu chảy qua từng Node một cách trực tiếp
    async for event in app.astream(user_input):
        # event là một dict có dạng: {"tên_node": {dữ liệu_trả_về}}
        for node_name, output in event.items():
            print(f"📍 Node vừa chạy xong: {node_name}")
            
            # Lấy tin nhắn cuối cùng được sinh ra ở Node này
            msg = output["messages"][-1]
            
            if msg.content:
                print(f"💬 Nội dung văn bản: {msg.content}")
            
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                print(f"🔍 AI ra lệnh gọi Tool: {msg.tool_calls[0]['name']}")
                print(f"📦 Tham số truyền vào: {msg.tool_calls[0]['args']}")

if __name__ == "__main__":
    asyncio.run(main())