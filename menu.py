import arcade
import arcade.gui

SCREEN_WIDTH = 960
SCREEN_HEIGHT = 544

class MenuView(arcade.View):
    def __init__(self):
        super().__init__()

        self.manager = arcade.gui.UIManager()
        self.manager.enable()

        button_start = arcade.gui.UIFlatButton(
            text="Play",
            width=250,
            height=60,
        )

        @button_start.event("on_click")
        def on_click(event):
            print("BUTTON WORKED")

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(
            anchor_x="left",
            anchor_y="bottom",
            child=button_start,
            align_x=SCREEN_WIDTH / 2 - button_start.width / 2,
            align_y=380
        )

        self.manager.add(anchor)

        button_exit = arcade.gui.UIFlatButton(
            text="Exit",
            width=250,
            height=60,
        )

        @button_exit.event("on_click")
        def on_click(event):
            arcade.close_window()

        anchor = arcade.gui.UIAnchorLayout()
        anchor.add(
            anchor_x="left",
            anchor_y="bottom",
            child=button_exit,
            align_x=SCREEN_WIDTH / 2 - button_exit.width / 2,
            align_y=280
        )

        self.manager.add(anchor)

    def on_draw(self):
        self.clear()
        arcade.draw_text(
            "Main Menu",
            SCREEN_WIDTH / 2,
            480,
            arcade.color.WHITE,
            40,
            anchor_x="center"
        )
        self.manager.draw()


window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, "GUI Test")
menu = MenuView()
window.show_view(menu)
arcade.run()