import os
import re
import base64
import zlib

                                  
PROTECTED_FILES = [
    "bot_core.py",
    "byte.py",
    "login_engine.py",
    "main.py",
    "RemoveFriend_Req_pb2.py",
    "thunderFF_pb2.py",
    "xC4.py",
    "xHeaders.py",
    "xP.py",
    "DEcwHisPErMsG_pb2.py",
    "dev_generator_pb2.py",
    "devxt_count_pb2.py",
    "Fo_pb2.py",
    "GenWhisperMsg_pb2.py",
    "GetFriend_Res_pb2.py",
    "join_spam_manager.py",
    "kyro_title_pb2.py",
    "MajoRLoGinrEq_pb2.py",
    "MajoRLoGinrEs_pb2.py",
    "PorTs_pb2.py",
    "room_join_pb2.py",
    "spam_join_pb2.py",
    "spam_request_pb2.py",
    "sQ_pb2.py",
    "Team_msg_pb2.py",
]

def process_file(filepath):
    if not os.path.exists(filepath):
        print(f"[-] File not found: {filepath}")
        return

    try:
                         
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

                                      
        match = re.search(r"_b64\.b85decode\('([^']+)'\)", content)
        if not match:
            print(f"[-] No encrypted code found in {filepath}")
            return

        enc_str = match.group(1)

                          
        decrypted_bytes = zlib.decompress(base64.b85decode(enc_str))
        decrypted_code = decrypted_bytes.decode("utf-8")

                                           
        with open(filepath + ".bak", "w", encoding="utf-8") as f:
            f.write(content)

                                                                           
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(decrypted_code)

        print(f"[+] Successfully Decrypted & Replaced: {filepath}")

    except Exception as e:
        print(f"[!] Error processing {filepath}: {e}")

if __name__ == "__main__":
    print("Starting Auto-Decrypt Process...\n")
    for file in PROTECTED_FILES:
        process_file(file)
    
    print("\n✅ All files processed successfully!")
    print("Original files are backed up as '.bak' files if you need to revert.")