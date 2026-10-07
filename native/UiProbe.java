import java.awt.Component;
import java.awt.Container;
import java.awt.Window;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import javax.swing.AbstractButton;
import javax.swing.JLabel;
import javax.swing.JTabbedPane;
import javax.swing.SwingUtilities;
import javax.swing.text.JTextComponent;

/** Read-only public UI discovery. No transformers, model access, or UI setters. */
public final class UiProbe {
  private static Instrumentation instrumentation;
  private static Map<String,Class<?>> uiTypes = Map.of();
  private static Path directory;
  private static int count;

  public static void premain(String argument, Instrumentation value) throws Exception {
    instrumentation = value;
    directory = Path.of(argument).toAbsolutePath();
    if (!Files.isDirectory(directory)) throw new IllegalArgumentException("Probe directory missing");
    Thread worker = new Thread(() -> {
      try {
        String previous = "";
        for (int attempts = 0; attempts < 18000; attempts++) {
          Path request = directory.resolve("request.txt");
          if (Files.isRegularFile(request) && Files.size(request) < 32) {
            String token = Files.readString(request, StandardCharsets.UTF_8).trim();
            if (token.matches("[0-9]{1,6}") && !token.equals(previous)) {
              previous = token;
              Map<String,Object> result;
              try {
                result = inspect();
              } catch (Throwable error) {
                result = new LinkedHashMap<>();
                result.put("swing", List.of()); result.put("fx", List.of()); result.put("windows", List.of());
                result.put("errors", List.of(error.toString()));
              }
              result.put("token", token);
              Path temporary = directory.resolve("reply.tmp");
              Files.writeString(temporary, json(result), StandardCharsets.UTF_8);
              Files.move(temporary, directory.resolve("reply.json"), StandardCopyOption.REPLACE_EXISTING,
                  StandardCopyOption.ATOMIC_MOVE);
            }
          }
          Thread.sleep(100);
        }
      } catch (Throwable error) {
        error.printStackTrace();
      }
    }, "OffDayKit-read-only-UI-probe");
    worker.setDaemon(true);
    worker.start();
  }

  private static Class<?> loaded(String name) {
    return uiTypes.get(name);
  }

  private static Object read(Object object, Class<?> owner, String name) throws Exception {
    return owner.getMethod(name).invoke(object);
  }

  private static Map<String,Object> inspect() throws Exception {
    Map<String,Class<?>> snapshot = new LinkedHashMap<>();
    for (Class<?> type : instrumentation.getAllLoadedClasses()) snapshot.putIfAbsent(type.getName(), type);
    uiTypes = snapshot;
    Map<String,Object> result = new LinkedHashMap<>();
    List<Object> swing = new ArrayList<>(), fx = new ArrayList<>(), scenes = new ArrayList<>(), windows = new ArrayList<>();
    List<String> errors = new ArrayList<>();
    count = 0;
    // Do not create the EDT from premain: the vendor must initialize its own
    // UI threads and class-loader context before read-only discovery begins.
    boolean swingReady = Thread.getAllStackTraces().keySet().stream()
        .anyMatch(thread -> thread.isAlive() && thread.getName().startsWith("AWT-EventQueue"));
    boolean fxReady = Thread.getAllStackTraces().keySet().stream()
        .anyMatch(thread -> thread.isAlive() && thread.getName().equals("JavaFX Application Thread"));
    if (swingReady) {
      SwingUtilities.invokeAndWait(() -> {
        try {
          for (Window window : Window.getWindows()) {
            if (window.isShowing()) swing(window, swing, scenes, 0);
          }
        } catch (Throwable e) { errors.add("Swing: " + e); }
      });
    }
    Class<?> platform = loaded("javafx.application.Platform");
    if (platform != null && fxReady) {
      CountDownLatch ready = new CountDownLatch(1);
      Runnable inspectFx = () -> {
        try {
          Class<?> windowType = loaded("javafx.stage.Window");
          Class<?> sceneType = loaded("javafx.scene.Scene");
          if (windowType != null && sceneType != null) {
            for (Object window : (Iterable<?>) windowType.getMethod("getWindows").invoke(null)) {
              if (Boolean.TRUE.equals(read(window, windowType, "isShowing"))) {
                Map<String,Object> record = new LinkedHashMap<>();
                record.put("class", window.getClass().getName());
                record.put("bounds", List.of(read(window, windowType, "getX"), read(window, windowType, "getY"),
                    read(window, windowType, "getWidth"), read(window, windowType, "getHeight")));
                record.put("focused", read(window, windowType, "isFocused"));
                Class<?> stageType = loaded("javafx.stage.Stage");
                if (stageType != null && stageType.isInstance(window)) record.put("title", read(window, stageType, "getTitle"));
                windows.add(record);
                scenes.add(read(window, windowType, "getScene"));
              }
            }
            IdentityHashMap<Object,Boolean> seen = new IdentityHashMap<>();
            for (Object scene : scenes) {
              if (scene != null && seen.put(scene, true) == null) {
                node(read(scene, sceneType, "getRoot"), fx, 0);
              }
            }
          }
        } catch (Throwable e) { errors.add("JavaFX: " + e); }
        finally { ready.countDown(); }
      };
      platform.getMethod("runLater", Runnable.class).invoke(null, inspectFx);
      if (!ready.await(8, TimeUnit.SECONDS)) throw new IllegalStateException("JavaFX discovery deadline");
    }
    result.put("swing", swing); result.put("fx", fx); result.put("windows", windows); result.put("errors", errors);
    return result;
  }

  private static void swing(Component component, List<Object> output, List<Object> scenes, int depth) throws Exception {
    if (!component.isShowing() || depth > 50 || ++count > 20000) return;
    Map<String,Object> item = new LinkedHashMap<>();
    item.put("class", component.getClass().getName());
    item.put("name", component.getName()); item.put("enabled", component.isEnabled());
    java.awt.Point point = component.getLocationOnScreen();
    item.put("bounds", List.of(point.x, point.y, component.getWidth(), component.getHeight()));
    if (component instanceof AbstractButton button) item.put("text", button.getText());
    if (component instanceof JLabel label) item.put("text", label.getText());
    if (component instanceof JTextComponent field) item.put("text", field.getText());
    if (component instanceof java.awt.Frame frame) item.put("title", frame.getTitle());
    if (component instanceof java.awt.Dialog dialog) item.put("title", dialog.getTitle());
    if (component instanceof JTabbedPane tabs) {
      List<String> titles = new ArrayList<>();
      for (int i = 0; i < tabs.getTabCount(); i++) titles.add(tabs.getTitleAt(i));
      item.put("tabs", titles);
    }
    Class<?> panel = loaded("javafx.embed.swing.JFXPanel");
    if (panel != null && panel.isInstance(component)) scenes.add(read(component, panel, "getScene"));
    output.add(item);
    if (component instanceof Container parent) {
      for (Component child : parent.getComponents()) swing(child, output, scenes, depth + 1);
    }
  }

  private static void node(Object value, List<Object> output, int depth) throws Exception {
    if (value == null || depth > 50 || ++count > 20000) return;
    Class<?> node = loaded("javafx.scene.Node"), parent = loaded("javafx.scene.Parent");
    if (!Boolean.TRUE.equals(read(value, node, "isVisible"))) return;
    Class<?> boundsType = loaded("javafx.geometry.Bounds");
    Object local = read(value, node, "getBoundsInLocal");
    Object bounds = node.getMethod("localToScreen", boundsType).invoke(value, local);
    Map<String,Object> item = new LinkedHashMap<>();
    item.put("class", value.getClass().getName()); item.put("id", read(value, node, "getId"));
    item.put("uid", System.identityHashCode(value));
    item.put("styles", read(value, node, "getStyleClass").toString());
    item.put("accessibleText", read(value, node, "getAccessibleText"));
    item.put("disabled", read(value, node, "isDisabled"));
    if (bounds != null) item.put("bounds", List.of(read(bounds, boundsType, "getMinX"),
        read(bounds, boundsType, "getMinY"), read(bounds, boundsType, "getWidth"), read(bounds, boundsType, "getHeight")));
    for (String typeName : List.of("javafx.scene.control.Labeled", "javafx.scene.control.TextInputControl", "javafx.scene.text.Text")) {
      Class<?> type = loaded(typeName);
      if (type != null && type.isInstance(value)) item.put("text", read(value, type, "getText"));
    }
    Class<?> label = loaded("javafx.scene.control.Label");
    if (label != null && label.isInstance(value)) {
      Object target = read(value, label, "getLabelFor");
      if (target != null) item.put("labelForUid", System.identityHashCode(target));
    }
    Class<?> cell = loaded("javafx.scene.control.Cell");
    if (cell != null && cell.isInstance(value)) {
      Object cellItem = read(value, cell, "getItem");
      item.put("item", cellItem == null ? null : cellItem.toString());
      item.put("itemClass", cellItem == null ? null : cellItem.getClass().getName());
    }
    output.add(item);
    if (parent.isInstance(value)) {
      for (Object child : (Iterable<?>) read(value, parent, "getChildrenUnmodifiable")) node(child, output, depth + 1);
    }
  }

  private static String json(Object value) {
    if (value == null) return "null";
    if (value instanceof Boolean) return value.toString();
    if (value instanceof Number number) return Double.isFinite(number.doubleValue()) ? value.toString() : "null";
    if (value instanceof Map<?,?> map) {
      List<String> parts = new ArrayList<>();
      for (Map.Entry<?,?> entry : map.entrySet()) parts.add(json(entry.getKey().toString()) + ":" + json(entry.getValue()));
      return "{" + String.join(",", parts) + "}";
    }
    if (value instanceof Iterable<?> list) {
      List<String> parts = new ArrayList<>(); for (Object item : list) parts.add(json(item));
      return "[" + String.join(",", parts) + "]";
    }
    StringBuilder result = new StringBuilder("\"");
    for (char ch : value.toString().toCharArray()) {
      if (ch == '\\' || ch == '"') result.append('\\').append(ch);
      else if (ch < 32) result.append(String.format("\\u%04x", (int) ch));
      else result.append(ch);
    }
    return result.append('"').toString();
  }
}
