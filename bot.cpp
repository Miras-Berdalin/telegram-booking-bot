#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <cstdlib>

using namespace std;

// ===== ВСТАВЬ СВОЙ НОВЫЙ ТОКЕН =====
string TOKEN = "8715700469:AAEnKFSNxeVt9yg8Y0uQsDgehGWKzeXcu_U";
string BASE_URL = "https://api.telegram.org/bot" + TOKEN + "/";

// ===== ВСТАВЬ ID ГРУППЫ (пример: -1001234567890) =====
string ADMIN_GROUP_ID = "-5155431438";

bool waitingForDate = false;

void sendMessage(string chat_id, string text) {
    string cmd =
    "curl -s -X POST \"" + BASE_URL + "sendMessage\" "
    "--data-urlencode \"chat_id=" + chat_id + "\" "
    "--data-urlencode \"text=" + text + "\"";

    system(cmd.c_str());
}

void answerCallback(string callback_id) {
    string cmd =
    "curl -s -X POST \"" + BASE_URL + "answerCallbackQuery\" "
    "--data-urlencode \"callback_query_id=" + callback_id + "\"";

    system(cmd.c_str());
}

void sendMainMenu(string chat_id) {

    string cmd =
    "curl -s -X POST \"" + BASE_URL + "sendMessage\" "
    "--data-urlencode \"chat_id=" + chat_id + "\" "
    "--data-urlencode \"text=Выберите пункт меню:\" "
    "--data-urlencode \"reply_markup={\\\"inline_keyboard\\\":["
    "[{\\\"text\\\":\\\"📅 Бронь\\\",\\\"callback_data\\\":\\\"bron\\\"}],"
    "[{\\\"text\\\":\\\"💰 Прайс\\\",\\\"callback_data\\\":\\\"price\\\"}],"
    "[{\\\"text\\\":\\\"🎨 Портфолио\\\",\\\"callback_data\\\":\\\"portfolio\\\"}]"
    "]}\"";

    system(cmd.c_str());
}

int main() {

    cout << "Bot started...\n";
    long offset = 0;

    while (true) {

        string cmd = "curl -s \"" + BASE_URL +
                     "getUpdates?offset=" + to_string(offset) +
                     "\" | jq -c '.result[]' > update.txt";

        system(cmd.c_str());

        FILE* file = fopen("update.txt", "r");

        if (file) {

            char buffer[4096];

            while (fgets(buffer, sizeof(buffer), file)) {

                string update = buffer;

                // update_id
                string id_cmd = "echo '" + update + "' | jq '.update_id'";
                FILE* id_pipe = popen(id_cmd.c_str(), "r");
                long update_id;
                fscanf(id_pipe, "%ld", &update_id);
                pclose(id_pipe);
                offset = update_id + 1;

                // chat_id (для message и callback)
                string chat_cmd = "echo '" + update + "' | jq -r '.message.chat.id // .callback_query.message.chat.id'";
                FILE* chat_pipe = popen(chat_cmd.c_str(), "r");
                char chat_buffer[1024] = {0};
                fgets(chat_buffer, sizeof(chat_buffer), chat_pipe);
                pclose(chat_pipe);
                string chat_id = chat_buffer;

                // message text
                string text_cmd = "echo '" + update + "' | jq -r '.message.text'";
                FILE* text_pipe = popen(text_cmd.c_str(), "r");
                char text_buffer[1024] = {0};
                fgets(text_buffer, sizeof(text_buffer), text_pipe);
                pclose(text_pipe);
                string text = text_buffer;

                // callback data
                string cb_cmd = "echo '" + update + "' | jq -r '.callback_query.data'";
                FILE* cb_pipe = popen(cb_cmd.c_str(), "r");
                char cb_buffer[1024] = {0};
                fgets(cb_buffer, sizeof(cb_buffer), cb_pipe);
                pclose(cb_pipe);
                string callback = cb_buffer;

                // callback id
                string cbid_cmd = "echo '" + update + "' | jq -r '.callback_query.id'";
                FILE* cbid_pipe = popen(cbid_cmd.c_str(), "r");
                char cbid_buffer[1024] = {0};
                fgets(cbid_buffer, sizeof(cbid_buffer), cbid_pipe);
                pclose(cbid_pipe);
                string callback_id = cbid_buffer;

                // ===== ЛОГИКА =====

                if (text.find("/start") != string::npos) {
                    sendMainMenu(chat_id);
                }

                else if (callback.find("bron") != string::npos) {
                    answerCallback(callback_id);
                    waitingForDate = true;
                    sendMessage(chat_id, "Введите дату брони (например: 12 марта 2026)");
                }

                else if (waitingForDate && text.length() > 2) {

                    string bookingInfo =
                        "🔥 Новая бронь\n\n"
                        "👤 User ID: " + chat_id +
                        "\n📅 Дата: " + text +
                        "\n\nНажмите кнопку ниже для подтверждения";

                    string group_cmd =
                    "curl -s -X POST \"" + BASE_URL + "sendMessage\" "
                    "--data-urlencode \"chat_id=" + ADMIN_GROUP_ID + "\" "
                    "--data-urlencode \"text=" + bookingInfo + "\" "
                    "--data-urlencode \"reply_markup={\\\"inline_keyboard\\\":["
                    "[{\\\"text\\\":\\\"✅ Подтвердить\\\",\\\"callback_data\\\":\\\"approve_" + chat_id + "\\\"}]"
                    "]}\"";

                    system(group_cmd.c_str());

                    sendMessage(chat_id, "Заявка отправлена на рассмотрение ⏳");
                    waitingForDate = false;
                }

                else if (callback.find("approve_") != string::npos) {

                    answerCallback(callback_id);

                    // извлекаем user_id
                    string approvedUserID = callback.substr(8);

                    sendMessage(approvedUserID,
                        "🎉 Ваша заявка утверждена ✅");

                    sendMessage(ADMIN_GROUP_ID,
                        "✅ Заявка подтверждена для User ID: " + approvedUserID);
                }

                else if (callback.find("price") != string::npos) {
                    answerCallback(callback_id);
                    sendMessage(chat_id, "Инфографика — 5000₸\nДизайн — 7000₸");
                }

                else if (callback.find("portfolio") != string::npos) {
                    answerCallback(callback_id);
                    sendMessage(chat_id, "https://yourportfolio.com");
                }
            }

            fclose(file);
        }

        this_thread::sleep_for(chrono::seconds(2));
    }

    return 0;
}