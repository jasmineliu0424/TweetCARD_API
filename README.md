# TweetCARD_API

### 摘要
Tweet C.A.R.D. 是一款開放程式應用介面（Open Application Programming Interface，Open API）的服務，APP的開發者、銀行端與TSP業者都能串接此「***信用卡推薦 API***」，讓使用者能獲得更個人化的推薦結果。此推薦API會將使用者依據其 **基本資訊**、**優惠偏好**和**消費金額** 找尋相似用戶，並根據消費者的 **定位地點** 與 **當下的環境因素**（例如：時間、移動速度），來推薦最符合消費者當下需求的信用卡。

目前我們致力於在兩個主要的時刻做推薦，分別是「***辦理信用卡***」與「***使用信用卡消費***」這兩個與信用卡最高度相關的時刻。

在辦理信用卡的時刻中，我們注重在兩種情境，分別是：「消費者對目前所在地點產生辦卡慾望」，以及「消費者單純想了解有哪些合適的卡可以辦」。

在使用信用卡消費的時刻中， 由於信用卡的優惠種類過於龐雜，較難在短時間內全面顧及，因此我們根據SocialLab在2018年熱門卡別種類統計中，挑選了幾項消費者最常使用的種類來進行推薦，分別是：**現金回饋**、**紅利回饋**、**停車優惠**、**加油優惠**及**電影優惠**，並且藉由不同的消費行為（例如：購物、停車、加油等）來劃分消費時刻。

另外，我們提供了「***信用卡分析介面***」給銀行，銀行可藉由此Dashboard，去檢視自家的信用卡出現在推薦結果上的頻率、使用者常使用的信用卡、常去的店家等資訊，有助於銀行分析潛在客群、得出自家信用卡和同業之間的競爭力，以及評估未來可以合作的店家，作為未來銀行金融相關業務發展策略的參考。

經由這款API，我們將能與多個商家APP、TSP業者、銀行進行串接，透過資料的共享，更加了解顧客的背景與需求。我們期望能在使用者產生消費意圖的情境當下就準確地滿足需求，不僅縮短使用者的決策時間，更促進了使用者對我們推薦系統API的使用頻率，進而提升使用者對串接端APP的依賴度。

### Abstract
Tweet C.A.R.D. is an Open Application Programming Interface (Open API) service that allows app developers, banks, and TSP operators to integrate the '***Credit Card Recommendation API***,' enabling users to receive more personalized recommendations. This recommendation API identifies similar users based on their ***demographic data, reward preference, and monthly expense***. It also considers the ***user's location and current time*** to recommend the credit card that best meets their needs.

Currently, we focus on providing recommendations at two key moments: ***'applying for a credit card'*** and ***'making purchases with a credit card,'*** both of which are highly relevant to credit card usage.

When applying for a credit card, we concentrate on two scenarios: 'the consumer develops a desire to apply for a card based on their current location,' and 'the consumer simply wants to explore suitable card options.'

In the context of making purchases with a credit card, due to the overwhelming variety of credit card rewards, it’s challenging to cover all options comprehensively in a short time. Therefore, based on the 2018 popular card types statistics from SocialLab, we selected a few of the most frequently used categories for recommendations: ***cashback, reward points, parking discounts, fuel discounts, and movie discounts***. We also categorize purchase moments based on different consumer behaviors (e.g., shopping, parking, fueling, etc.).

Additionally, we provide a ***'Credit Card Analysis Interface'*** for banks. Through this dashboard, banks can monitor how often their credit cards appear in recommendation results, which cards are frequently used by users, popular stores, and more. This helps banks analyze potential customer segments, assess their cards' competitiveness against other banks, and evaluate future partnership opportunities with merchants, serving as a reference for future financial business development strategies.

Through this API, we can connect with multiple merchant apps, TSP operators, and banks. By sharing data, we can gain a deeper understanding of customer backgrounds and needs. Our goal is to accurately meet user needs at the moment they have the intent to make a purchase, not only shortening their decision-making time but also increasing the frequency of our recommendation system API’s use, thereby enhancing user dependence on the apps.
