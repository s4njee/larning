# Qt 6 Mastery Study Guide

A comprehensive, job-focused guide to mastering Qt 6. This guide focuses on the modules that show up most in real Qt work: desktop UI, the model/view architecture, QML/Qt Quick, networking, data access, concurrency, media, device integration, and the production concerns (styling, internationalization, deployment) that turn a demo into a shipped app. Every module section includes runnable code. Build real apps, not toy examples.

If you are learning PySide6 instead of C++, keep the same module order. The APIs and architecture are identical; only the syntax changes, and the key sections below show both. There is a dedicated PySide6 track at the end.

---

## Phase 1: Core Application Foundations

### 1.1 Qt Core

- **What it is**: The non-graphical foundation of Qt. `Qt Core` gives you the event loop, object model, signals and slots, the meta-object system, properties, containers, I/O, JSON, timers, threads, and the resource system
  - This is the module everything else builds on, so fluency here pays off across Widgets, Qt Quick, networking, database code, and testing; docs: [Qt Core](https://doc.qt.io/qt-6/qtcore-index.html).
- **Key classes to know**: `QObject`, `QString`, `QByteArray`, `QVariant`, `QList`, `QHash`, `QFile`, `QDir`, `QTimer`, `QDateTime`, `QSettings`, `QJsonDocument`
  - Start with `QObject`, `QTimer`, `QFile`, `QSettings`, and the JSON types first because they show up in almost every nontrivial Qt app.
  - Treat `QVariant` and the container types as Qt's portability layer between modules, serialization, models, and UI bindings.
- **Core patterns**: parent-child ownership, signals/slots, the meta-object system, event-driven design, `Q_PROPERTY`, bindable properties, resource files (`.qrc`), implicit sharing
  - Understanding ownership rules is the fastest way to avoid leaks, dangling pointers, and double-deletes in Qt code.

#### Signals and slots

Signals and slots are Qt's type-safe observer mechanism. Prefer the **function-pointer connection syntax** — it is checked at compile time, supports lambdas, and refactors cleanly:

```cpp
class Worker : public QObject {
    Q_OBJECT                                  // required for signals/slots and the meta-object
public:
    using QObject::QObject;
signals:
    void progress(int percent);               // signals are declared, never defined
public slots:
    void start() {
        for (int i = 0; i <= 100; i += 25)
            emit progress(i);                 // 'emit' is a no-op marker; it just calls connected slots
    }
};

Worker worker;
QObject::connect(&worker, &Worker::progress, &worker, [](int pct) {
    qDebug() << "progress" << pct;            // argument types are verified by the compiler
});
worker.start();
```

A connection's *type* controls delivery. Within one thread the call is direct (synchronous). When sender and receiver live on different threads, Qt automatically uses a **queued** connection — the call is posted to the receiver's event loop and runs on the receiver's thread. You can force either with `Qt::DirectConnection` / `Qt::QueuedConnection`. This is the single most important thing to understand before writing threaded Qt code.

#### The meta-object system (moc)

The `Q_OBJECT` macro is not decoration. At build time Qt's **Meta-Object Compiler (moc)** scans your headers and generates a `.cpp` with the machinery behind signals/slots, run-time type info (`qobject_cast`, `metaObject()`), properties, and `QML_ELEMENT` registration. CMake's `qt_standard_project_setup()` enables `AUTOMOC`, so this happens transparently — but when you see a linker error about an "undefined vtable" or a signal that "isn't a member," the usual cause is a missing `Q_OBJECT` or a stale moc run.

#### Bindable properties (Qt 6)

Qt 6 added `QProperty<T>` — reactive values that re-compute automatically, no signal wiring required. Expose them through `Q_PROPERTY(... BINDABLE ...)`:

```cpp
class Thermostat : public QObject {
    Q_OBJECT
    Q_PROPERTY(double target READ target WRITE setTarget BINDABLE bindableTarget)
public:
    double target() const { return m_target; }
    void setTarget(double t) { m_target = t; }
    QBindable<double> bindableTarget() { return &m_target; }
private:
    QProperty<double> m_target{20.0};
};

Thermostat t;
QProperty<QString> label;
label.setBinding([&] { return QStringLiteral("Target: %1°C").arg(t.bindableTarget().value()); });
qDebug() << label.value();   // "Target: 20°C"
t.setTarget(22.5);
qDebug() << label.value();   // "Target: 22.5°C" — recomputed, no connect() in sight
```

- **Build pattern**:

```cmake
find_package(Qt6 REQUIRED COMPONENTS Core)
target_link_libraries(app PRIVATE Qt6::Core)
```

- **In PySide6**, signals are first-class and even more concise:

```python
from PySide6.QtCore import QObject, Signal, Slot

class Worker(QObject):
    progress = Signal(int)

    @Slot()
    def start(self):
        for i in range(0, 101, 25):
            self.progress.emit(i)

w = Worker()
w.progress.connect(lambda pct: print("progress", pct))
w.start()
```

- **Practice**: Build a small CLI or headless service that reads JSON config, watches a directory, emits signals on file changes, and persists user settings with `QSettings`. Keep it UI-free so you are forced to understand the event loop, object ownership, and signal-driven design directly.

`Qt Core` is the part of Qt that changes how you think about application structure. Once signals, timers, object trees, the meta-object system, and event delivery feel natural, the rest of the framework stops looking like a giant class catalog and starts reading like layers built on one runtime model.

---

### 1.2 Qt GUI

- **What it is**: The low-level graphical foundation for windows, events, images, fonts, painting, and input
  - Widgets and Qt Quick sit on top of `Qt GUI`, so this is where you learn what a window is, how painting works, and how Qt handles images and text; docs: [Qt GUI](https://doc.qt.io/qt-6/qtgui-index.html).
- **Key classes to know**: `QGuiApplication`, `QWindow`, `QScreen`, `QImage`, `QPixmap`, `QPainter`, `QFont`, `QClipboard`
  - `QPainter`, `QImage`, and `QPixmap` matter more than the rest early on because they explain most rendering and image-handling behavior in Qt.
  - Learn how `QScreen` and high-DPI behavior interact before you attempt custom visual polish across platforms.
- **Most useful concepts**: device-independent pixels, paint events, coordinate systems, text rendering, drag and drop, high-DPI scaling
- **Custom painting** happens in a paint event with a `QPainter`:

```cpp
void Canvas::paintEvent(QPaintEvent *) {
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    p.fillRect(rect(), Qt::white);
    p.setPen(QPen(Qt::darkBlue, 2));
    for (const QRectF &r : m_regions)         // m_regions are in widget coordinates
        p.drawRect(r);
    p.setPen(Qt::black);
    p.drawText(rect(), Qt::AlignCenter, QStringLiteral("%1 regions").arg(m_regions.size()));
}
```

- **Important distinction**: `QImage` is best for CPU-side image manipulation (pixel access, filters, threads), while `QPixmap` is optimized for showing images on screen. Mixing them up is behind a surprising number of performance bugs.
- **Use it for**: custom painting, image processing, low-level rendering, clipboard integration, custom cursors, and direct window handling.
- **Practice**: Build a simple image annotation tool with zoom, pan, and custom overlay drawing using `QPainter`. Add one feature that forces coordinate conversion, such as selecting regions or drawing handles, so the exercise teaches more than simple painting.

What the bullets cannot fully convey is that `Qt GUI` is where Qt stops being "widgets and controls" and becomes a rendering framework. Even if you spend most of your time in Widgets or Quick, this layer explains why painting glitches, DPI bugs, and image performance issues behave the way they do.

---

### 1.3 Qt Widgets

- **What it is**: The classic desktop UI toolkit in Qt
  - Use Widgets when you need dense desktop interfaces, document-style apps, native-feeling admin tools, or long-lived enterprise UIs; docs: [Qt Widgets](https://doc.qt.io/qt-6/qtwidgets-index.html).
- **Key classes to know**: `QWidget`, `QMainWindow`, `QDialog`, `QFormLayout`, `QTableView`, `QTreeView`, `QDockWidget`, `QAction`, `QMenu`, `QToolBar`
  - Learn `QMainWindow`, `QAction`, and the model/view widgets together because that combination defines a large percentage of serious desktop Qt software.
- **Most important patterns**: model/view, action-driven menus and toolbars, dialog composition, Designer `.ui` files, reusable custom widgets
- **An action drives a menu item, a toolbar button, and a shortcut from one object**:

```cpp
auto *window = new QMainWindow;
auto *view   = new QTableView;
view->setModel(proxy);                 // a model/view frontend (see 1.4)
view->setSortingEnabled(true);
window->setCentralWidget(view);

auto *addAction = new QAction(QIcon(QStringLiteral(":/icons/add.svg")), "&Add Item", window);
addAction->setShortcut(QKeySequence::New);
QObject::connect(addAction, &QAction::triggered, window, [=] { openEditDialog(); });

window->menuBar()->addMenu("&File")->addAction(addAction);
window->addToolBar("Main")->addAction(addAction);   // same action, two surfaces, one handler
window->show();
```

- **Watch out for**: putting business logic directly inside widgets. The best Widgets apps keep models, services, and domain logic separate so the UI stays replaceable and testable.
- **Practice**: Build a small desktop inventory app with a `QMainWindow`, table view, edit dialog, menu bar, toolbar, and persistent window state (`QSettings` for `saveGeometry`/`restoreGeometry`). Add sorting, filtering, and save/restore of geometry so it feels like a real desktop tool instead of a form demo.

What bullets miss here is that Widgets rewards architectural discipline more than visual experimentation. Teams that do well with Widgets usually keep the UI boring in a good way and invest instead in model quality, workflow speed, and long-term maintainability.

---

### 1.4 Model/View Architecture

- **What it is**: Qt's framework for separating data (a *model*) from its presentation (a *view*), connected by indexes and roles. This is the single most important architectural concept in Qt and the one most under-taught — it powers `QTableView`, `QTreeView`, `QListView`, and QML's `ListView`/`Repeater` alike; docs: [Model/View Programming](https://doc.qt.io/qt-6/model-view-programming.html).
- **Why it matters**: Once your data lives in a `QAbstractItemModel`, every Qt view can display, sort, filter, and edit it without copying it into widgets. The same model feeds a desktop table and a QML list.
- **Key classes**: `QAbstractListModel`, `QAbstractTableModel`, `QAbstractItemModel`, `QModelIndex`, `QSortFilterProxyModel`, `QStyledItemDelegate`, and the ready-made `QStringListModel`, `QStandardItemModel`, `QSqlTableModel`.

A custom table model needs only a handful of overrides:

```cpp
struct Item { QString name; int qty; };

class InventoryModel : public QAbstractTableModel {
    Q_OBJECT
public:
    enum Column { Name, Qty, ColumnCount };
    using QAbstractTableModel::QAbstractTableModel;

    int rowCount(const QModelIndex & = {}) const override { return m_rows.size(); }
    int columnCount(const QModelIndex & = {}) const override { return ColumnCount; }

    QVariant data(const QModelIndex &idx, int role) const override {
        if (!idx.isValid() || role != Qt::DisplayRole) return {};
        const Item &it = m_rows[idx.row()];
        return idx.column() == Name ? QVariant(it.name) : QVariant(it.qty);
    }

    QVariant headerData(int section, Qt::Orientation o, int role) const override {
        if (o != Qt::Horizontal || role != Qt::DisplayRole) return {};
        return section == Name ? "Name" : "Qty";
    }

    void addItem(const Item &it) {
        beginInsertRows({}, m_rows.size(), m_rows.size());
        m_rows.push_back(it);
        endInsertRows();                       // every attached view updates itself
    }
private:
    QList<Item> m_rows;
};
```

**Sorting and filtering are free** — wrap the model in a proxy instead of re-querying:

```cpp
auto *proxy = new QSortFilterProxyModel(view);
proxy->setSourceModel(inventory);
proxy->setFilterCaseSensitivity(Qt::CaseInsensitive);
proxy->setFilterKeyColumn(InventoryModel::Name);
view->setModel(proxy);
QObject::connect(searchBox, &QLineEdit::textChanged,
                 proxy, &QSortFilterProxyModel::setFilterFixedString);
```

**The same model drives QML.** Expose named roles via `roleNames()`, and QML delegates reference them by name:

```cpp
enum Roles { NameRole = Qt::UserRole + 1, QtyRole };
QHash<int, QByteArray> roleNames() const override {
    return { {NameRole, "name"}, {QtyRole, "qty"} };   // data() should also switch on these
}
```
```qml
ListView {
    model: inventory                 // a context property or registered singleton
    delegate: Text { text: name + " × " + qty }   // 'name' and 'qty' come from roleNames()
}
```

- **Watch out for**: forgetting `begin*/end*` calls around mutations (views won't update, or will crash), and doing heavy work inside `data()` (it is called constantly during scrolling — keep it cheap).
- **Use a delegate** (`QStyledItemDelegate`) when a cell needs a custom editor or custom painting, such as a progress bar or a combo box.
- **Practice**: Take the inventory app from 1.3 and back it with a real `QAbstractTableModel` plus a `QSortFilterProxyModel`. Then bind the *same* model to a QML `ListView` to prove the separation pays off.

The real lesson is that model/view is less about widgets than about owning your data in one place. When the model is the source of truth, sorting, filtering, multiple views, and UI migrations stop being rewrites and become configuration.

---

### 1.5 Qt Network

- **What it is**: Qt's cross-platform networking layer for HTTP, TCP, UDP, TLS, and general socket work
  - Most production Qt apps talk to something outside the process, so `Qt Network` becomes core infrastructure very quickly; docs: [Qt Network](https://doc.qt.io/qt-6/qtnetwork-index.html).
- **Key classes to know**: `QNetworkAccessManager`, `QNetworkRequest`, `QNetworkReply`, `QTcpSocket`, `QTcpServer`, `QUdpSocket`, `QSslSocket`
  - `QNetworkAccessManager` and the request/reply types are the first things to master because they cover most HTTP client work in Qt applications.
- **An authenticated GET, parsed into the model, with the reply cleaned up**:

```cpp
auto *nam = new QNetworkAccessManager(this);
QNetworkRequest req(QUrl("https://api.example.com/items"));
req.setRawHeader("Authorization", "Bearer " + token);

QNetworkReply *reply = nam->get(req);
connect(reply, &QNetworkReply::finished, this, [this, reply] {
    reply->deleteLater();                         // replies are never auto-deleted
    if (reply->error() != QNetworkReply::NoError) {
        emit loadFailed(reply->errorString());
        return;
    }
    const auto doc = QJsonDocument::fromJson(reply->readAll());
    populateModel(doc.array());
});
```

- **Most important patterns**: centralize request creation, wrap replies in service classes, set explicit timeouts (`QNetworkRequest::setTransferTimeout`), handle retries and auth refresh in one place.
- **Watch out for**: blocking the UI thread and scattering network code across widgets or QML files. Networking should feel like a service layer, not a bunch of ad hoc lambdas attached to buttons.
- **Practice**: Build an API client that performs authenticated requests, parses JSON into a model, retries transient failures, and surfaces errors cleanly to the UI. Add a small error taxonomy so you separate transport failures from application-level failures.

The subtle idea here is that good Qt networking code is mostly architecture, not sockets. The difference between a maintainable app and a brittle one is usually whether network behavior was designed as a coherent service boundary or copied piecemeal into presentation code.

---

## Phase 2: Declarative UI Stack

### 2.1 Qt Qml

- **What it is**: The QML language runtime and integration layer between QML, JavaScript, and C++
  - `Qt Qml` is what lets you register C++ types, expose services to QML, structure QML modules, and keep declarative UI connected to real application logic; docs: [Qt Qml](https://doc.qt.io/qt-6/qtqml-index.html).
- **Key classes to know**: `QQmlApplicationEngine`, `QQmlEngine`, `QQmlContext`, `QQmlComponent`, and the registration macros `QML_ELEMENT` / `QML_SINGLETON`.
- **Registering a C++ type for QML** is now declarative — annotate the class and list it in the QML module:

```cpp
class ApiClient : public QObject {
    Q_OBJECT
    QML_ELEMENT                          // moc + the build system make this importable from QML
    Q_PROPERTY(bool loading READ loading NOTIFY loadingChanged)
public:
    using QObject::QObject;
    bool loading() const { return m_loading; }
    Q_INVOKABLE void refresh();          // callable directly from QML
signals:
    void loadingChanged();
private:
    bool m_loading = false;
};
```

```cmake
qt_add_qml_module(app
    URI Acme.App
    VERSION 1.0
    QML_FILES Main.qml Dashboard.qml
    SOURCES apiclient.cpp apiclient.h
)
```

```qml
import Acme.App
ApiClient { id: api; Component.onCompleted: api.refresh() }
```

- **Most important patterns**: `qt_add_qml_module()`, explicit type registration over context properties, singleton services, clean C++/QML boundaries.
- **Watch out for**: overusing context properties. Context-property-heavy apps are harder to test, harder to navigate, and easier to break during refactors than apps built from explicit QML modules.
- **Practice**: Expose a C++ service that fetches data and a list model that QML can bind to, then package both into a real QML module with a clear namespace.

What the bullet points only hint at is that `Qt Qml` is really an architectural boundary tool. It decides how disciplined your separation is between declarative presentation and application logic, and that separation matters far more over time than any one QML syntax feature.

---

### 2.2 Qt Quick

- **What it is**: The standard library for writing QML user interfaces
  - `Qt Quick` gives you the visual canvas, input handling, models/views, states, transitions, loaders, and animation system behind modern QML applications; docs: [Qt Quick](https://doc.qt.io/qt-6/qtquick-index.html).
- **Key types to know**: `Item`, `Rectangle`, `Text`, `Image`, `ListView`, `GridView`, `Repeater`, `Loader`, `State`, `Transition`, `Behavior`, `PropertyAnimation`
- **A data-backed list with navigation**, the backbone of most Quick apps:

```qml
ListView {
    anchors.fill: parent
    model: deviceModel                 // a C++ model exposed from Qt
    spacing: 4
    delegate: ItemDelegate {
        width: ListView.view.width
        text: model.name
        onClicked: stack.push(detailPage, { deviceId: model.id })
    }
}
```

- **States and transitions** keep visual logic declarative instead of imperative:

```qml
Rectangle {
    id: card
    state: api.loading ? "loading" : "ready"
    states: State { name: "loading"; PropertyChanges { target: spinner; running: true } }
    transitions: Transition { NumberAnimation { properties: "opacity"; duration: 150 } }
}
```

- **Watch out for**: putting too much logic in QML JavaScript. QML should own presentation and interaction flow; heavy logic, I/O, and business rules belong in C++.
- **Practice**: Build a responsive dashboard with animated tiles, a list/detail flow, and view states for loading, error, and empty results. Force yourself to extract reusable components instead of keeping one giant page file.

The harder-to-express idea is that Qt Quick is less about drawing rectangles and more about building a reactive scene graph with disciplined state changes. Teams that succeed with Quick think in components, bindings, and model-driven views, not in imperative UI mutation.

---

### 2.3 Qt Quick Controls

- **What it is**: Prebuilt controls and app-shell primitives for Qt Quick
  - `Qt Quick Controls` saves you from hand-building every input, dialog, page container, and navigation surface in QML; docs: [Qt Quick Controls](https://doc.qt.io/qt-6/qtquickcontrols-index.html).
- **Key types to know**: `ApplicationWindow`, `Page`, `StackView`, `Button`, `TextField`, `ComboBox`, `Popup`, `Dialog`, `Drawer`, `Menu`, `ToolBar`
- **The app shell** — a window, a header, and a navigation stack — is just a few lines:

```qml
import QtQuick.Controls
ApplicationWindow {
    visible: true; width: 480; height: 800
    header: ToolBar {
        Label { text: stack.currentItem.title ?? "App"; anchors.centerIn: parent }
    }
    StackView { id: stack; anchors.fill: parent; initialItem: settingsPage }
    Component { id: settingsPage; Page { property string title: "Settings" /* ... */ } }
}
```

- **Watch out for**: deep control customization before you understand the styling model (see 2.5). Learn the default control behavior first, then customize intentionally so you do not end up fighting the framework.
- **Practice**: Build a multi-page settings app with validation, modal dialogs, toolbar actions, and a themed control set. Add one custom-styled control only after the base flow works so you can compare framework defaults with your customization cost.

What bullets cannot show well is that `Qt Quick Controls` is where product consistency starts. It gives Quick apps the boring but essential structure of windows, pages, dialogs, and controls that let a UI feel shipped instead of merely animated.

---

### 2.4 Qt Quick Layouts

- **What it is**: Layout managers for arranging Qt Quick items predictably
  - `Qt Quick Layouts` is one of the most practical modules in the entire QML stack because it keeps UIs from collapsing into hand-positioned coordinates and anchor spaghetti; docs: [Qt Quick Layouts](https://doc.qt.io/qt-6/qtquicklayouts-index.html).
- **Key types**: `RowLayout`, `ColumnLayout`, `GridLayout`, plus attached properties like `Layout.fillWidth`, `Layout.preferredWidth`, and `Layout.alignment`.
- **Real sizing behavior lives in the attached properties**, not the containers:

```qml
import QtQuick.Layouts
ColumnLayout {
    anchors.fill: parent; spacing: 8
    TextField { Layout.fillWidth: true; placeholderText: "Name" }
    RowLayout {
        Layout.fillWidth: true
        Button { text: "Cancel"; Layout.fillWidth: true }
        Button { text: "Save";   Layout.fillWidth: true; Layout.preferredWidth: 200 }
        // both expand, but Save claims more of the extra space via its larger preferred width
    }
}
```

- **Most important concepts**: implicit size, preferred size, fill behavior, stretch ratios, and when to choose layouts over anchors.
- **Watch out for**: mixing anchors and layouts carelessly on the same item — many Quick sizing bugs come from combining two layout systems without a clear boundary.
- **Practice**: Rebuild an existing anchored QML screen using layouts only, then resize-test it across phone, tablet, and desktop form factors. Include long translated text or unusual window sizes so the exercise surfaces real-world breakpoints.

The underlying idea is that layout discipline is one of the biggest separators between a demo UI and a production UI. Many Qt Quick teams lose time not because layouts are hard, but because they postpone layout structure until visuals are already tangled together.

---

### 2.5 Styling and Theming

- **What it is**: The two distinct ways Qt skins a UI — **Qt Style Sheets (QSS)** for Widgets, and the **Quick Controls styles** for QML. They do not overlap, and picking the right one per stack avoids a lot of wasted effort; docs: [Qt Style Sheets](https://doc.qt.io/qt-6/stylesheet.html), [Styling Qt Quick Controls](https://doc.qt.io/qt-6/qtquickcontrols-styles.html).
- **Widgets use CSS-like stylesheets**, applied per-widget or app-wide via `qApp->setStyleSheet()`:

```css
/* app.qss */
QPushButton           { background: #2d6cdf; color: white; border-radius: 6px; padding: 6px 14px; }
QPushButton:hover     { background: #3b7ae6; }
QPushButton:disabled  { background: #9aa7bd; }
QLineEdit[invalid="true"] { border: 1px solid #d23; }   /* selects on a dynamic property */
```

  The dynamic-property selector needs a re-polish after you change the property:

```cpp
edit->setProperty("invalid", true);
edit->style()->polish(edit);     // re-evaluate the stylesheet for this widget
```

- **Qt Quick Controls pick a style** at startup (Basic, Fusion, Material, Universal, or a custom one). Choose it with an env var or in code, then theme via attached properties:

```bash
QT_QUICK_CONTROLS_STYLE=Material ./app
```

```qml
import QtQuick.Controls.Material
ApplicationWindow {
    Material.theme: Material.Dark
    Material.accent: Material.Teal
}
```

- **Watch out for**: heavy per-widget stylesheets (they cascade and can hurt performance), and assuming a Quick `Material` property works under the `Basic` style — style-specific attached properties are no-ops under other styles.
- **Practice**: Theme the inventory app two ways — a light/dark QSS for the Widgets build, and Material light/dark for a Quick build — and add a runtime toggle for each.

The point is that theming is a stack-level decision, not a late coat of paint. Knowing which system applies, and keeping theme values in one place, is what lets a Qt app ship a consistent look without per-screen hacks.

---

## Phase 3: Data, Concurrency, and Testing

### 3.1 Qt SQL

- **What it is**: Qt's database integration layer for SQL backends
  - `Qt SQL` is especially useful when you need SQLite locally or want model/view-friendly data access in Widgets apps; docs: [Qt SQL](https://doc.qt.io/qt-6/qtsql-index.html).
- **Key classes to know**: `QSqlDatabase`, `QSqlQuery`, `QSqlRecord`, `QSqlTableModel`, `QSqlRelationalTableModel`, `QSqlQueryModel`
- **Prepared statements inside a transaction** are the baseline for correctness and speed:

```cpp
QSqlDatabase db = QSqlDatabase::addDatabase("QSQLITE");
db.setDatabaseName("inventory.db");
if (!db.open())
    qFatal("db: %s", qPrintable(db.lastError().text()));

QSqlQuery q;
q.prepare("INSERT INTO items (name, qty) VALUES (?, ?)");
db.transaction();
for (const Item &it : batch) {
    q.addBindValue(it.name);
    q.addBindValue(it.qty);
    if (!q.exec()) { db.rollback(); break; }
}
db.commit();                          // one fsync instead of N — orders of magnitude faster
```

- **`QSqlTableModel` plugs straight into a view** when you want editable rows without hand-written SQL — it *is* a `QAbstractItemModel`, so everything from 1.4 applies.
- **Watch out for**: assuming database connections are thread-agnostic. Each thread needs its own connection; sharing one across threads is undefined behavior.
- **Most important patterns**: prepared statements, transactions, repository wrappers, schema migration strategy, per-thread connection management.
- **Practice**: Build a small SQLite-backed inventory or notes app with transactions, search, and a `QTableView` (via `QSqlTableModel`) or a QML list model. Include one schema migration so you practice maintaining state over time, not just querying a fresh database.

The real lesson is that database code in Qt is less about tables than boundaries. When SQL, models, threading, and UI are separated cleanly, the app stays understandable; when they are mixed, every new feature becomes a debugging exercise.

---

### 3.2 Concurrency: Qt Concurrent and QThread

- **What it is**: Two layers of background work — `Qt Concurrent` for fire-and-forget tasks over a thread pool, and `QThread` with the worker-object pattern for long-lived background objects; docs: [Qt Concurrent](https://doc.qt.io/qt-6/qtconcurrent-index.html), [QThread](https://doc.qt.io/qt-6/qthread.html).
- **Reach for `Qt Concurrent` first.** It runs a callable on the global thread pool and hands back a `QFuture`; a `QFutureWatcher` marshals the result back onto the UI thread:

```cpp
QFuture<int> future = QtConcurrent::run([path] { return countLines(path); });

auto *watcher = new QFutureWatcher<int>(this);
connect(watcher, &QFutureWatcher<int>::finished, this, [this, watcher] {
    showResult(watcher->result());      // runs on the UI thread — safe to touch widgets
    watcher->deleteLater();
});
watcher->setFuture(future);
```

- **Use `QThread` + a worker object** when the task is a stateful, long-running service (a device poller, an indexer) rather than a one-shot computation. The rule: the worker `moveToThread`, then *only* communicate via signals.

```cpp
auto *thread = new QThread;
auto *worker = new Indexer;            // no parent — ownership moves with the thread
worker->moveToThread(thread);

connect(thread, &QThread::started,  worker, &Indexer::run);
connect(worker, &Indexer::finished, thread, &QThread::quit);
connect(thread, &QThread::finished, worker, &QObject::deleteLater);
connect(thread, &QThread::finished, thread, &QObject::deleteLater);
thread->start();
// From now on, never call worker's methods directly — emit a signal it's connected to.
```

- **Watch out for**: touching UI objects or thread-affine resources from worker code. Concurrency here protects responsiveness; it does not make thread affinity optional. Subclassing `QThread` and overriding `run()` is the legacy pattern — prefer the worker-object approach above.
- **Practice**: Build a background file indexer that scans folders, reports progress, supports cancellation (`QFutureWatcher::cancel` or a worker flag), and streams incremental results into the UI. Make cancellation visible in the design instead of bolting it on later.

What the list cannot fully capture is that responsiveness is a product feature, not an implementation detail. These tools give you a safe default path to responsive software before you need to invent a custom threading model.

---

### 3.3 Qt Test

- **What it is**: Qt's unit testing and benchmarking framework
  - `Qt Test` is the right way to verify signal-slot behavior, event-driven logic, data-driven cases, and many async workflows that plain assertion libraries do not understand as cleanly; docs: [Qt Test](https://doc.qt.io/qt-6/qttest-index.html).
- **Key tools**: `QCOMPARE`, `QVERIFY`, data-driven tests (`QTest::addColumn`/`QFETCH`), benchmarks, `QSignalSpy`, GUI event helpers.
- **Data-driven tests plus a signal spy** cover most of what makes Qt code distinctive:

```cpp
class TestParser : public QObject {
    Q_OBJECT
private slots:
    void counts_data() {
        QTest::addColumn<QByteArray>("input");
        QTest::addColumn<int>("expected");
        QTest::newRow("empty") << QByteArray("")     << 0;
        QTest::newRow("two")   << QByteArray("a\nb") << 2;
    }
    void counts() {
        QFETCH(QByteArray, input);
        QFETCH(int, expected);
        QCOMPARE(countLines(input), expected);     // runs once per row above
    }
    void emitsFinalProgress() {
        Worker w;
        QSignalSpy spy(&w, &Worker::progress);     // capture emissions
        w.start();
        QVERIFY(spy.count() >= 1);
        QCOMPARE(spy.last().at(0).toInt(), 100);   // last progress was 100%
    }
};
QTEST_MAIN(TestParser)
#include "test_parser.moc"
```

- **Watch out for**: flaky tests caused by implicit event-loop assumptions. Event-driven code needs explicit waits (`QSignalSpy::wait`, `QTRY_COMPARE`) so tests fail for real reasons, not timing.
- **Practice**: Add tests around a service layer, a widget dialog, and one async operation using `QSignalSpy` and data-driven cases. Include one negative-path test for timeout, validation, or failure UI so the suite is not only testing happy flows.

The deeper idea is that Qt tests become valuable when they mirror the framework's event-driven nature. Good suites do not just assert values; they verify state changes, signals, timing boundaries, and user-visible outcomes.

---

## Phase 4: Frequently Used Specialized Modules

### 4.1 Qt Multimedia

- **What it is**: Audio, video, camera, and capture APIs for Qt applications
  - Reach for `Qt Multimedia` when the app needs playback, recording, camera feeds, or media capture without depending on a separate media stack; docs: [Qt Multimedia](https://doc.qt.io/qt-6/qtmultimedia-index.html).
- **Key classes to know**: `QMediaPlayer`, `QAudioOutput`, `QAudioInput`, `QCamera`, `QMediaCaptureSession`, `QVideoSink`
- **Playback wires a player to separate audio and video outputs** (a Qt 6 change from Qt 5's all-in-one player):

```cpp
auto *player = new QMediaPlayer(this);
auto *audio  = new QAudioOutput(this);
player->setAudioOutput(audio);
player->setVideoOutput(videoWidget);                 // a QVideoWidget or QML VideoOutput
player->setSource(QUrl::fromLocalFile(path));
connect(player, &QMediaPlayer::errorOccurred, this,
        [](QMediaPlayer::Error, const QString &msg) { qWarning() << msg; });
player->play();
```

- **Most important patterns**: separate playback state from UI state, test codecs on target platforms, and wrap device selection in a service layer.
- **Watch out for**: backend and codec differences across operating systems. Multimedia code that works on your laptop still needs validation on the exact machines or hardware you ship to.
- **Practice**: Build a small media player or camera capture app with device selection, playback controls, and error handling. Test at least two environments so the practice includes platform variability rather than just API use.

The important non-bullet idea is that multimedia is one of the least abstract parts of Qt. It touches real devices, codecs, drivers, and OS backends, so design quality is tied directly to how early you validate on the target environment.

---

### 4.2 Qt SVG

- **What it is**: Rendering and display support for SVG vector graphics
  - `Qt SVG` matters more than it first appears because icons, diagrams, badges, and scalable artwork show up in nearly every polished Qt app; docs: [Qt SVG](https://doc.qt.io/qt-6/qtsvg-index.html).
- **Key classes to know**: `QSvgRenderer`, `QSvgWidget`
- **Render an SVG to a crisp pixmap at any target size** — the whole point of vector assets:

```cpp
QSvgRenderer renderer(QStringLiteral(":/icons/logo.svg"));
QPixmap pm(64, 64);
pm.fill(Qt::transparent);
QPainter p(&pm);
renderer.render(&p);                  // sharp at 64px, 128px, or any DPI
button->setIcon(QIcon(pm));
```

- **Most important patterns**: keep icon assets consistent, render to the right target size, and test complex third-party SVG files early.
- **Watch out for**: assuming full browser-grade SVG support. Qt covers common app assets very well, but validate complex files instead of trusting them blindly.
- **Practice**: Replace a PNG icon set with SVG assets and build a small icon previewer that supports light and dark themes plus several size previews, so you catch assets that render but do not stay readable at small UI scales.

The broader lesson is that visual quality often depends on asset discipline more than fancy rendering code. `Qt SVG` gives you scalability, but only if the team treats icons and illustrations as part of the product system.

---

### 4.3 Qt Serial Port

- **What it is**: Cross-platform access to physical and virtual serial ports
  - A must-learn for embedded tools, device configuration utilities, industrial software, or any app that talks directly to hardware; docs: [Qt Serial Port](https://doc.qt.io/qt-6/qtserialport-index.html).
- **Key classes to know**: `QSerialPort`, `QSerialPortInfo`
- **Discover ports first**, instead of hard-coding names:

```cpp
for (const QSerialPortInfo &info : QSerialPortInfo::availablePorts())
    qDebug() << info.portName() << info.description() << info.manufacturer();
```

- **Then treat the wire as a byte stream and build framing on top** — reads do *not* arrive as whole messages:

```cpp
QSerialPort port;
port.setPortName("/dev/ttyUSB0");
port.setBaudRate(QSerialPort::Baud115200);
if (!port.open(QIODevice::ReadWrite)) { /* handle and bail */ }

connect(&port, &QSerialPort::readyRead, this, [this, &port] {
    m_buffer += port.readAll();                  // arbitrary-sized chunks
    int nl;
    while ((nl = m_buffer.indexOf('\n')) != -1) {
        const QByteArray frame = m_buffer.left(nl);
        m_buffer.remove(0, nl + 1);
        handleFrame(frame);                      // exactly one complete line
    }
});
```

- **Most important patterns**: isolate protocol parsing, buffer partial frames, reconnect cleanly, log raw traffic, and keep the transport separate from the UI.
- **Practice**: Build a serial console that supports connect/disconnect, text and hex views, timestamps, and message parsing. Add malformed-input handling so the parser recovers instead of only consuming ideal traffic.

The main idea bullets miss is that serial work is mostly about failure tolerance. Robust serial tools expect partial reads, unplug events, resets, and corrupted frames from the start, not as an afterthought.

---

### 4.4 Qt WebSockets

- **What it is**: WebSocket client and server support for real-time communication
  - One of the easiest ways to add push updates, collaborative features, or live telemetry to a Qt app without polling; docs: [Qt WebSockets](https://doc.qt.io/qt-6/qtwebsockets-index.html).
- **Key classes to know**: `QWebSocket`, `QWebSocketServer`
- **A client with exponential-backoff reconnect** — the part that separates a toy from a product:

```cpp
auto *ws = new QWebSocket;
connect(ws, &QWebSocket::connected, this, [this] { m_backoff = 1000; });   // reset on success
connect(ws, &QWebSocket::textMessageReceived, this, &Client::onMessage);
connect(ws, &QWebSocket::disconnected, this, [this, ws] {
    QTimer::singleShot(m_backoff, this, [this, ws] { ws->open(m_url); });
    m_backoff = qMin(m_backoff * 2, 30000);     // double up to a 30s cap
});
ws->open(m_url);
```

- **Most important patterns**: reconnect with backoff, heartbeat/ping handling, JSON message envelopes, message versioning, and connection-state UI.
- **Watch out for**: treating connection lifecycle as an afterthought. Real-time features feel solid only when reconnect, transient errors, and stale sessions are designed up front.
- **Practice**: Build a live metrics viewer that reconnects automatically, charts incoming data, and shows connection health in the UI. Include an intentional disconnect simulation so reconnect logic is exercised on purpose.

The key idea is that real-time UX is as much about degraded behavior as connected behavior. A WebSocket feature feels professional only when the user can understand stale data, reconnecting state, and transport health at a glance.

---

## Phase 5: Production Concerns

These are the topics that separate a working demo from shippable software. They are easy to defer and expensive to retrofit, so practice them on a small app before you need them on a large one.

### 5.1 Internationalization

- **What it is**: Qt's translation system — mark strings, extract them, translate them in Qt Linguist, and load the result at runtime; docs: [Qt Linguist](https://doc.qt.io/qt-6/qtlinguist-index.html), [Internationalization](https://doc.qt.io/qt-6/internationalization.html).
- **Mark every user-facing string** with `tr()` (C++) or `qsTr()` (QML). The plural-aware form handles count agreement automatically:

```cpp
label->setText(tr("Save changes?"));
status->setText(tr("%n file(s) copied", "status bar", count));   // %n picks the right plural form
```

```qml
Text { text: qsTr("Save changes?") }
```

- **The toolchain** is three commands — extract, translate, compile:

```bash
lupdate app.pro -ts translations/app_fr.ts   # scan sources, collect tr() strings
linguist translations/app_fr.ts              # translate in the Qt Linguist GUI
lrelease translations/app_fr.ts              # compile .ts -> binary .qm
```

- **Load the translation before building the UI**:

```cpp
QApplication app(argc, argv);
QTranslator translator;
if (translator.load(":/i18n/app_" + QLocale::system().name() + ".qm"))
    app.installTranslator(&translator);
```

- **Watch out for**: string concatenation (it breaks word order in other languages — use `%1` placeholders), and baking layout widths around English text. Test with a long-word language and a right-to-left locale early.

### 5.2 Building and Deployment

- **What it is**: Turning source into a redistributable binary. Modern Qt 6 standardizes on **CMake**; deployment uses a per-platform tool that copies the Qt libraries and plugins your app actually uses; docs: [Building with CMake](https://doc.qt.io/qt-6/cmake-get-started.html), [Deploying Qt Applications](https://doc.qt.io/qt-6/deployment.html).
- **A minimal modern CMake project**:

```cmake
cmake_minimum_required(VERSION 3.21)
project(app LANGUAGES CXX)

find_package(Qt6 REQUIRED COMPONENTS Core Widgets Sql)
qt_standard_project_setup()                  # C++17, plus AUTOMOC / AUTORCC / AUTOUIC
qt_add_executable(app main.cpp inventorymodel.cpp)
target_link_libraries(app PRIVATE Qt6::Core Qt6::Widgets Qt6::Sql)
```

  `qt_standard_project_setup()` is what enables `AUTOMOC` — the automatic moc run from 1.1 that makes `Q_OBJECT` and `QML_ELEMENT` work without manual build steps.
- **Bundle for each platform** with the matching tool:

```bash
windeployqt app.exe          # Windows: copies Qt DLLs + plugins beside the .exe
macdeployqt app.app -dmg     # macOS: bundles frameworks into the .app, optionally builds a .dmg
# Linux: use linuxdeployqt or your distro's packaging — Qt ships no single official tool
pyside6-deploy main.py       # PySide6: one-command standalone bundle (via Nuitka)
```

- **Watch out for**: forgetting plugins (image formats, SQL drivers, and platform plugins live in separate plugin folders the deploy tools handle for you — manual copies usually miss them), and code signing/notarization, which is mandatory on macOS and increasingly expected on Windows.
- **Practice**: Take one small app all the way to a double-clickable artifact on your own OS, then translate it into one other language and confirm the `.qm` loads in the deployed build — not just from your IDE.

The theme of this phase is that "done" means *installed and readable in another language on a machine that is not yours*. Practicing the last mile on something small is far cheaper than discovering missing plugins or broken layouts on your flagship app.

---

## Capstone Projects

Build these to demonstrate job-ready Qt skills. Finish each one by internationalizing it (5.1) and producing a deployable artifact (5.2) — that final 10% is what proves you can ship, not just prototype.

### Project 1: Desktop Operations Console

- **Stack**: `Qt Widgets`, Model/View, `Qt Network`, `Qt SQL`, `Qt SVG`, `Qt Test`
  - This stack forces you to combine desktop workflow design, a real data model, service boundaries, storage, and testability in one application.
- **Build**: A multi-panel desktop app with login, searchable model-backed tables, edit dialogs, persistent settings, and API-backed data sync
  - Treat sync as a service layer and the tables as `QAbstractItemModel` frontends rather than placing everything in window classes.
- **Why it matters**: This mirrors the dense internal desktop tools many Qt teams ship. If you can make it feel stable and maintainable, you have most of the instincts needed for traditional enterprise Qt work.

### Project 2: Touch-Friendly Control Panel

- **Stack**: `Qt Qml`, `Qt Quick`, `Qt Quick Controls`, `Qt Quick Layouts`, styling (Material), `Qt WebSockets`
  - This mix reflects the declarative, themed, and real-time concerns of embedded dashboards and operator interfaces.
- **Build**: A responsive dashboard with page navigation, live status cards, alert banners, a light/dark theme toggle, and reconnection behavior
  - Make the interface adapt across at least two form factors so layout and state design get exercised under stress.
- **Why it matters**: This is close to how embedded panels, operator consoles, and modern Qt product UIs are built. It shows you can connect a polished reactive front end to real transport and state management.

### Project 3: Device Configuration & Capture Tool

- **Stack**: `Qt Widgets` or `Qt Quick`, `Qt Serial Port`, Qt Concurrent / `QThread`, `Qt Multimedia`, `Qt Core`
  - Valuable because it crosses the usual boundaries between UI, concurrency, device I/O, and media capture.
- **Build**: An app that detects a device, configures it over serial on a background thread, captures media or logs, and saves structured results locally
  - Keep transport, parsing, capture, and persistence in separate layers so the project stays understandable as features grow.
- **Why it matters**: It combines hardware communication, async work, and media handling — a very real Qt skill mix — and surfaces the platform and hardware behavior that simple CRUD projects never expose.

The capstones matter because Qt fluency is easiest to demonstrate in integrated apps, not isolated feature demos. Hiring teams care less that you touched ten modules separately and more that you can combine a few of them into software with clear architecture and realistic behavior.

---

## Study Methodology

1. **Choose one UI stack early**: Learn either `Qt Widgets` or `Qt Quick` first, then add the other later. Trying to master both at once slows down the part that actually ships products.
2. **Master `Qt Core` and Model/View before chasing UI polish**: Signals/slots, ownership, the event loop, and `QAbstractItemModel` are the foundation. Most Qt bugs that look visual are really state-management or lifecycle bugs.
3. **Keep business logic out of the UI layer**: Whether you use Widgets or QML, keep services, models, and domain logic separate. This makes testing easier and keeps rewrites or UI migrations realistic.
4. **Prefer CMake and modern Qt 6 patterns**: `find_package()`, `qt_standard_project_setup()`, `qt_add_executable()`, and `qt_add_qml_module()` should feel normal. Learn the current defaults instead of building habits around legacy tooling.
5. **Use official examples aggressively**: Qt's example code is one of the fastest ways to learn module idioms and naming patterns. Study how Qt authors structure signals, model classes, and UI composition.
6. **Test async and signal-heavy code early**: Add `Qt Test` with `QSignalSpy` while the code is still small. Signal timing, retries, and background work are much easier to fix before they spread across the app.
7. **Validate on target platforms early**: Networking, serial, multimedia, scaling, styling, and deployment can all vary by OS or hardware. Qt is cross-platform, but product polish still depends on platform-specific verification.
8. **Build small real apps continuously, and finish them**: Ship tiny utilities, dashboards, viewers, and editors — translated and packaged — as you learn each module. A working, deployed tool teaches more than another pass through the class reference.

The point of the methodology is sequencing, not perfection. Qt gets much easier when you stop trying to learn every module equally and instead build a layered mental model: foundation and data model first, one UI path second, integration and testing third, specialized modules and production concerns only when a real app demands them.

---

## Focus Tracks

### C++ Desktop Track

- **Best for**: native-feeling desktop software, internal tools, CAD-style interfaces, admin panels, and long-lived business applications
  - Ideal when product value comes from workflow depth, dense information display, and years of maintainability rather than visual novelty.
- **Primary stack**: `Qt Core`, `Qt GUI`, `Qt Widgets`, Model/View, `Qt Network`, `Qt SQL`, `Qt Test`
  - Emphasizes stability, data-heavy workflows, and mature desktop interaction over custom animated presentation.
- **Learn in this order**: signals/slots and ownership first, then `QMainWindow`, model/view, dialogs, persistence, network services, and testing
  - That order keeps architecture ahead of chrome, which is usually the right tradeoff for serious desktop work.
- **What to delay**: custom painting-heavy work, deep stylesheet theming, and QML integration until the fundamentals feel routine.
- **Why this path works**: it gets you productive fastest if your target is traditional desktop software with dense data entry and tables.

This track aligns with where Qt has been strongest for years: practical desktop software with long lifetimes. If your goal is "ship a stable internal or commercial desktop tool," this path minimizes distractions and builds the habits that matter most first.

### QML / Embedded Track

- **Best for**: touch interfaces, device dashboards, kiosks, automotive-like HMIs, and animated control panels
  - Fits best when the UI must communicate system state continuously and presentation quality is part of the product itself.
- **Primary stack**: `Qt Core`, Model/View, `Qt Qml`, `Qt Quick`, `Qt Quick Controls`, `Qt Quick Layouts`, styling, then `Qt Network` and `Qt WebSockets`
  - The sequence matters because a reactive visual layer is only sustainable when the backend contract and component structure are disciplined.
- **Learn in this order**: QML bindings and component composition first, then layouts, controls, styling, backend integration, states/transitions, and performance tuning
  - Reverse that order and chase animation first, and you usually end up with beautiful but fragile QML.
- **What to emphasize**: responsive layouts, startup time, asset handling, and keeping heavy logic in C++ instead of inline QML JavaScript.
- **Why this path works**: it matches how modern Qt teams build custom, fluid UIs on embedded and cross-platform products.

This path is strongest when the UI is part of the product identity rather than a shell around forms. It teaches the discipline needed for declarative front ends to stay maintainable under real-time state, animation, and device constraints.

### PySide6 Track

- **Best for**: Python-first developers, rapid internal tooling, scientific apps, automation-heavy desktop software, and teams that want Qt UI power without switching their whole stack to C++
  - Especially strong when existing Python code, libraries, or domain expertise matter more than extracting every last bit of native performance.
- **Core idea**: learn the same Qt architecture as the C++ path, but write it in Python through the official Qt for Python bindings
  - The underlying module model is identical, so nearly all of this guide applies directly; docs: [Qt for Python](https://doc.qt.io/qtforpython-6/), [Getting Started](https://doc.qt.io/qtforpython-6/gettingstarted.html).
- **Recommended learning order**:
  1. `PySide6.QtCore`
  2. `PySide6.QtGui`
  3. `PySide6.QtWidgets`
  4. Model/View (`QAbstractTableModel`, `QSortFilterProxyModel`)
  5. `PySide6.QtNetwork`
  6. `PySide6.QtSql`
  7. `PySide6.QtTest`
  8. `PySide6.QtQml` and `PySide6.QtQuick` if you want QML later
- **A minimal Widgets app** shows how close the Python is to the C++:

```python
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTableView
from PySide6.QtCore import QAbstractTableModel, Qt

class InventoryModel(QAbstractTableModel):
    def __init__(self, rows):
        super().__init__()
        self._rows = rows                      # list of (name, qty)

    def rowCount(self, parent=None): return len(self._rows)
    def columnCount(self, parent=None): return 2

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            return self._rows[index.row()][index.column()]

app = QApplication(sys.argv)
view = QTableView()
view.setModel(InventoryModel([("Bolt", 120), ("Nut", 340)]))
win = QMainWindow(); win.setCentralWidget(view); win.show()
sys.exit(app.exec())
```

- **Environment setup**:
  - Use a virtual environment for every app; install with `pip install pyside6`.
  - Keep Python and PySide6 versions pinned for reproducible builds.
  - Qt for Python wheels already include the Qt binaries, so a separate Qt install is not required for the normal `pip` workflow.
- **Python-specific differences to internalize early**:
  - Signals and slots feel natural in Python, but object lifetime still follows Qt ownership rules — keep references to objects you expect to live.
  - You still must respect the UI thread; Python does not make widget access from worker threads safe.
  - Long-running Python code can still freeze the UI, so background work and clear service boundaries matter just as much as in C++.
  - Type hints on service and model layers pay off quickly in larger apps.
- **Designer and code generation**: build `.ui` forms with `pyside6-designer`, convert with `pyside6-uic`, compile resources with `pyside6-rcc`; docs: [Qt for Python Tools](https://doc.qt.io/qtforpython-6/tools/index.html).
- **Deployment**: run from the venv during development, then test `pyside6-deploy` early instead of at the end; docs: [pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html).
- **When to choose PySide6 over C++ Qt**: choose PySide6 when developer speed, the Python ecosystem, scripting, data tooling, or automation matter more than maximum native performance; choose C++ Qt when startup time, low-level integration, memory control, or systems-level performance is the top constraint.

The important idea beyond the bullets is that PySide6 is most effective when treated as Qt first and Python second. Teams get the best results when they keep Qt architecture — event-driven design, ownership, model/view, and service boundaries — intact instead of assuming the Python binding turns the framework into a generic scriptable GUI toolkit.

---

## Additional Reference Links

- **Architecture and core**:
  - [All Modules](https://doc.qt.io/qt-6/qtmodules.html)
  - [Qt Core](https://doc.qt.io/qt-6/qtcore-index.html)
  - [The Meta-Object System](https://doc.qt.io/qt-6/metaobjects.html)
  - [Signals & Slots](https://doc.qt.io/qt-6/signalsandslots.html)
  - [Qt Bindable Properties](https://doc.qt.io/qt-6/bindableproperties.html)
  - [Model/View Programming](https://doc.qt.io/qt-6/model-view-programming.html)
- **UI**:
  - [Qt GUI](https://doc.qt.io/qt-6/qtgui-index.html)
  - [Qt Widgets](https://doc.qt.io/qt-6/qtwidgets-index.html)
  - [Qt Qml](https://doc.qt.io/qt-6/qtqml-index.html)
  - [Qt Quick](https://doc.qt.io/qt-6/qtquick-index.html)
  - [Qt Quick Controls](https://doc.qt.io/qt-6/qtquickcontrols-index.html)
  - [Qt Style Sheets](https://doc.qt.io/qt-6/stylesheet.html)
- **Data, concurrency, and testing**:
  - [Qt SQL](https://doc.qt.io/qt-6/qtsql-index.html)
  - [Qt Concurrent](https://doc.qt.io/qt-6/qtconcurrent-index.html)
  - [QThread](https://doc.qt.io/qt-6/qthread.html)
  - [Qt Test](https://doc.qt.io/qt-6/qttest-index.html)
- **Devices and real-time**:
  - [Qt Serial Port](https://doc.qt.io/qt-6/qtserialport-index.html)
  - [Qt WebSockets](https://doc.qt.io/qt-6/qtwebsockets-index.html)
  - [Qt Multimedia](https://doc.qt.io/qt-6/qtmultimedia-index.html)
- **Production**:
  - [Internationalization with Qt](https://doc.qt.io/qt-6/internationalization.html)
  - [Qt Linguist Manual](https://doc.qt.io/qt-6/qtlinguist-index.html)
  - [Building with CMake](https://doc.qt.io/qt-6/cmake-get-started.html)
  - [Deploying Qt Applications](https://doc.qt.io/qt-6/deployment.html)
- **Qt for Python / PySide6**:
  - [Qt for Python Overview](https://doc.qt.io/qtforpython-6/)
  - [PySide6 Getting Started](https://doc.qt.io/qtforpython-6/gettingstarted.html)
  - [Qt for Python Tools](https://doc.qt.io/qtforpython-6/tools/index.html)
  - [pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html)
- **Good next modules after this guide**:
  - [Qt Graphics View Framework](https://doc.qt.io/qt-6/graphicsview.html) (2D canvas, items, scenes)
  - [Qt State Machine](https://doc.qt.io/qt-6/qtstatemachine-index.html)
  - [Qt Charts](https://doc.qt.io/qt-6/qtcharts-index.html)
  - [Qt Bluetooth](https://doc.qt.io/qt-6/qtbluetooth-index.html)
  - [Qt Quick 3D](https://doc.qt.io/qt-6/qtquick3d-index.html)
  - [Qt WebEngine](https://doc.qt.io/qt-6/qtwebengine-index.html)

Use the reference links as a map, not a substitute for building. The class index becomes far more useful after you have hit a real problem in one of your projects and need the exact Qt idiom or API family that solves it.
