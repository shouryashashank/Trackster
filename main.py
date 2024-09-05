import flet as ft
import time
import asyncio



# Open directory dialog
def get_directory_result(e: ft.FilePickerResultEvent):
    directory_path.value = e.path if e.path else "Cancelled!"
    directory_path.update()

get_directory_dialog = ft.FilePicker(on_result=get_directory_result)
directory_path = ft.Text()

def progress_bar():
    t = ft.Text(value="")
    t2 = ft.Text(value = "0")
    pb = ft.ProgressBar(value=0)

    async def button_clicked(e):
        t.value = "Downloading"
        await t.update_async()
        b.disabled = True
        await b.update_async()
        for i in range(0, 101):
            t2.value = i
            pb.value = i * 0.01
            await asyncio.sleep(0.1)
            await t2.update_async()
            await pb.update_async()
        t.value = ""
        t2.value = ""
        await t.update_async()
        b.disabled = False
        await b.update_async()

    b = ft.ElevatedButton("Download Playlist", width=200000, on_click=button_clicked)

    return ft.Column(
        [
            b,
            ft.Column([t, pb,t2])
            
        ],
        
    )


def drop_down():
    
    return ft.Dropdown(
            label="Song Exist Action",
            hint_text="What to do when that song already exist in your directory?",
            options=[
                ft.dropdown.Option("Replace all"),
                ft.dropdown.Option("Skip all"),
            ],
            autofocus=True,
        )
def app_bar():
    view = ft.AppBar(
        title=ft.Text("Trackster"),
        actions=[
            ft.IconButton(ft.icons.MENU, style=ft.ButtonStyle(padding=0))
        ],
        bgcolor=ft.colors.with_opacity(0.04, ft.cupertino_colors.SYSTEM_BACKGROUND),
    )
    return view


def nav_bar():
    view = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.icons.ONDEMAND_VIDEO_ROUNDED, label="Youtube"),
            ft.NavigationBarDestination(icon=ft.icons.MUSIC_NOTE, label="Spotify")
            
        ],
        border=ft.Border(
            top=ft.BorderSide(color=ft.cupertino_colors.SYSTEM_GREY2, width=0)
        ),
    )
    return view 


class FolderPicker(ft.Row):
    def build(self):
        view = ft.Row(
                [
                    ft.ElevatedButton(
                        "Select Folder",
                        icon=ft.icons.FOLDER_OPEN,
                        on_click=lambda _: get_directory_dialog.get_directory_path()
                    ),
                    directory_path,
                    # ft.Text(value="Select Output Direcotry to save the playlist", italic=False, selectable=False, style='labelSmall', ),
                ]
            )
        return view


def main(page: ft.Page):
    page.adaptive = True
    page.appbar = app_bar()
    page.navigation_bar = nav_bar()
    # hide all dialogs in overlay
    folder_picker = FolderPicker()
    url = ft.TextField(keyboard_type=ft.KeyboardType.TEXT)
    pb = ft.ProgressBar()
    page.overlay.extend([ get_directory_dialog])
    
    page.add(
        ft.SafeArea(
            ft.Column(
                [
                    ft.Divider(opacity=0, height= 20),
                    folder_picker,
                    ft.Divider(opacity=0, height= 20),
                    ft.Text("Enter Youtube playlist url:"),
                    url,
                    ft.Divider(opacity=0),  
                    drop_down(),
                    ft.Divider(opacity=0),
                    # ft.ElevatedButton(text="Download Playlist",width=200000),
                    ft.Divider(opacity=0),
                    progress_bar()
                ]
            )
        )
    )
    for i in range(0, 101):
            pb.value = i * 0.01
            time.sleep(0.1)
            page.update()


ft.app(target=main)